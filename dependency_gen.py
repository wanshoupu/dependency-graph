import argparse
import codecs
import json
import os
import queue
import re
import threading
from typing import Dict, Set

from data_structures import SourceNode, EdgeNode, CustomEncoder, TypeNode, RefType, CodeNode
from src_analyzer import src_proc

node_file = os.path.join(os.path.dirname(__file__), "types.txt")
edge_file = os.path.join(os.path.dirname(__file__), "type-dependencies.txt")

max_queue_size = 7
assembly_line = queue.Queue(max_queue_size)

include_regex = re.compile('#include\s+["<"](.*)[">]')
valid_headers = [['.h', '.hpp'], 'red']
valid_sources = [['.c', '.cc', '.cpp'], 'blue']
valid_extensions = valid_headers[0] + valid_sources[0]


def normalize(path):
    """ Return the name of the node that will represent the file at path. """
    filename = os.path.basename(path)
    end = filename.rfind('.')
    end = end if end != -1 else len(filename)
    return filename[:end]


def skip(entry):
    if '/tests/' in entry.path:
        return True
    if entry.is_file():
        _, ext = os.path.splitext(entry.path)
        if ext not in valid_extensions:
            return True

    return False


def find_code_files(path, recursive=True):
    """
    Return a list of all the files in the folder.
    If recursive is True, the function will search recursively.
    """
    # return ['/Users/swan/workspace/client/game-engine/Client/App/ads/include/ads/AdInstanceInterface.h',
    #         '/Users/swan/workspace/client/game-engine/Client/App/ads/include/ads/BackendAdsProvider.h',
    #         '/Users/swan/workspace/client/game-engine/Client/App/ads/include/ads/AdsProviderInterface.h']
    if os.path.exists(path) and os.path.isfile(path):
        return [path]
    files = []
    for entry in os.scandir(path):
        if skip(entry):
            continue
        if entry.is_dir() and recursive:
            files.extend(find_code_files(entry.path))
        else:
            files.append(entry.path)
    return files


def source_proc(root_dir):
    """
    return a tuple (includes, declares)
    includes: dict{src_file : set(includes)}
    declares: dict{src_file : dict{TypeNode : CodeNode}}
    """

    def worker():
        while True:
            src_file = assembly_line.get()
            src_name = SourceNode(os.path.basename(src_file))
            print(f'Processing {src_file}')
            ns, incls = src_proc(src_file)
            if ns:
                declares[src_name] = ns
            if incls:
                includes[src_name] = incls
            print(f'Finished {src_file}')
            assembly_line.task_done()

    includes = dict()
    declares = dict()
    print("process source files at capacity of {} threads".format(max_queue_size))
    ths = [threading.Thread(target=worker, daemon=True) for _ in range(max_queue_size)]
    for t in ths:
        t.start()

    for item in find_code_files(root_dir):
        assembly_line.put(item)
    assembly_line.join()

    print('All work completed')
    return includes, declares


def write_nodes(nodes, file=node_file):
    with open(file, "w") as fd:
        for node in nodes:
            json.dump(node, fd, cls=CustomEncoder)
            fd.write('\n')
    print(f'Saved nodes to {file}')


def write_edges(edges, file=edge_file):
    with open(file, "w") as fd:
        for edge in edges:
            json.dump({'caller': edge.caller.name, 'callee': edge.callee.name, 'refType': edge.refType.name}, fd)
            fd.write('\n')
    print(f'Saved edges to {file}')


def fieldMatch(statements, name):
    pattern = fr'\W*{name}\W*'
    for s in statements:
        if re.match(pattern, s) and s.find('(') < 0 and s.find(')') < 0:
            return True
    return False


def methodMatch(statements, name):
    pattern = fr'\W*{name}\W*'
    for s in statements:
        if re.match(pattern, s) and s.find('(') >= 0 and s.find(')') >= 0:
            return True
    return False


def symbol_search(code: CodeNode, types: Set[TypeNode]) -> Dict[TypeNode, RefType]:
    deps = dict()
    if code.inheritance_declare:
        for t in types:
            if code.inheritance_declare.find(t.name) >= 0:
                deps[t] = RefType.INHERITANCE

    if code.class_body:
        for t in types:
            pattern = fr'\b{t.name}\b'
            statements = [s for s in code.class_body.split(';') if re.findall(pattern, s)]
            if not statements:
                continue
            if all(s.find('(') < 0 and s.find(')') < 0 for s in statements):
                deps[t] = RefType.COMPOSITION
            else:
                deps[t] = RefType.METHOD

    return deps


def dep_analysis(folders):
    def get_included_types(src):
        included_types = set()
        for s in includes.get(src, set()):
            for ts in declares.get(s, dict()).keys():
                included_types.add(ts)
        return included_types

    includes = dict()
    declares = dict()
    for folder in folders:
        i, d = source_proc(folder)
        includes.update(i)
        declares.update(d)

    nodes = {k for v in declares.values() for k in v.keys()}
    edges = set()
    for src, types in declares.items():
        included_types = get_included_types(src)
        for t, code in types.items():
            # for each declared type t, search code for dependencies in included_types
            deps = symbol_search(code, included_types)
            for d, refType in deps.items():
                edges.add(EdgeNode(t, d, refType))
    return nodes, edges


def verify_data(nodes, edges):
    typeNames = dict()
    for n in nodes:
        assert n.name not in typeNames, f'Name conflict {n} <--> {typeNames[n.name]}'

    for edge in edges:
        caller = edge.caller
        callee = edge.callee
        assert caller in nodes, f'{caller} not found'
        assert callee in nodes, f'{callee} not found'
    referenced_nodes = set(e.callee for e in edges) | set(e.caller for e in edges)
    unref_nodes = nodes - referenced_nodes
    if unref_nodes:
        print(f'Here are unreferenced types: {unref_nodes}')

    print('Data verified and no anomaly found')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('folders', metavar='directory', nargs='+', help='Path to the folder(s) to scan for src')
    args = parser.parse_args()
    nodes, edges = dep_analysis(args.folders)
    verify_data(nodes, edges)
    write_nodes(nodes)
    write_edges(edges)
