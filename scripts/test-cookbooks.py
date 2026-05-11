#!/usr/bin/env python3
import json
import os
import sys

import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def load_yaml(path):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def inline_system(obj, base):
    system = obj.get('system')
    if isinstance(system, dict):
        text = system.get('text', '')
        if 'file' in system:
            file_path = os.path.join(base, system['file'])
            if not os.path.isfile(file_path):
                raise FileNotFoundError(f'system.file not found: {file_path}')
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
        append = system.get('append', '')
        if append:
            text = text + '\n\n' + append
        obj['system'] = text
    return obj


def resolve_manifest(file_path):
    base = os.path.dirname(file_path)
    data = load_yaml(file_path)
    if data is None:
        data = {}
    data = inline_system(data, base)
    if 'output_schema' in data:
        del data['output_schema']
    bodies = []
    if isinstance(data.get('callable_agents'), list):
        sub_ids = []
        for child in data['callable_agents']:
            manifest_rel = child.get('manifest')
            if not manifest_rel:
                continue
            child_path = os.path.join(base, manifest_rel)
            bodies.extend(resolve_manifest(child_path))
            name = os.path.splitext(os.path.basename(child_path))[0]
            sub_ids.append({'type': 'agent', 'id': f'DRYRUN_{name}', 'version': 'latest'})
        data['callable_agents'] = sub_ids
    bodies.append(data)
    return bodies


def main():
    errs_all = False
    cookbooks_dir = os.path.join(ROOT, 'managed-agent-cookbooks')
    for slug in sorted(os.listdir(cookbooks_dir)):
        d = os.path.join(cookbooks_dir, slug)
        if not os.path.isdir(d):
            continue
        try:
            bodies = resolve_manifest(os.path.join(d, 'agent.yaml'))
        except Exception as e:
            print(f'  ✗ {slug}: {e}', file=sys.stderr)
            errs_all = True
            continue
        try:
            json_text = json.dumps(bodies)
        except Exception as e:
            print(f'  ✗ {slug}: invalid JSON: {e}', file=sys.stderr)
            errs_all = True
            continue
        errs = []
        for i, body in enumerate(bodies):
            if not body.get('system'):
                errs.append(f"{body.get('name', '<unknown>')}: empty system")
            if i < len(bodies) - 1 and body.get('callable_agents'):
                errs.append(f"{body.get('name', '<unknown>')}: depth>1 (subagent has callable_agents)")
        if 'output_schema' in json_text:
            errs.append('output_schema leaked into a body')
        if errs:
            print(f'  ✗ {slug}', file=sys.stderr)
            for e in errs:
                print(f'      {e}', file=sys.stderr)
            errs_all = True
        else:
            print(f'  ✓ {slug:24s} {len(bodies)} bodies')
    return 1 if errs_all else 0


if __name__ == '__main__':
    sys.exit(main())
