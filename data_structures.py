import json
import os
import re
from enum import Enum


class RefType(Enum):
    INHERITANCE = 1
    COMPOSITION = 2
    METHOD = 3


class SourceType(Enum):
    HEADER = re.compile(r'\.h|\.hpp')
    CPP = re.compile(r'\.c|\.cc|\.cpp|\.c\+\+')

    @staticmethod
    def parseval(symbol):
        for item in list(SourceType):
            if re.fullmatch(item.value, symbol):
                return item


class TypeClassifier(Enum):
    ENUM = re.compile(r'enum(?: class)?')
    STRUCT = re.compile(r'struct')
    CLASS = re.compile(r'class')

    @staticmethod
    def parseval(symbol):
        for item in list(TypeClassifier):
            if re.fullmatch(item.value, symbol):
                return item


class TypeNode:
    def __init__(self, name, classifier: TypeClassifier, sourceName, sourceType: SourceType) -> None:
        # class name
        self.name = name

        self.sourceType = sourceType
        # file basename without extension
        self.sourceName = sourceName
        self.classifier = classifier

    def __hash__(self) -> int:
        return hash(self.name) ^ hash(self.sourceType) ^ hash(self.sourceName) ^ hash(self.classifier)

    def __eq__(self, other):
        if not isinstance(other, TypeNode):
            return False

        return (self.name == other.name
                and self.sourceType == other.sourceType
                and self.sourceName == other.sourceName
                and self.classifier == other.classifier)

    def __repr__(self) -> str:
        return self.name


class SourceNode:
    def __init__(self, srcFile) -> None:
        self.sourceName, self.sourceType = os.path.splitext(srcFile)

    def __hash__(self) -> int:
        return hash(self.sourceType) ^ hash(self.sourceName)

    def __eq__(self, other):
        if not isinstance(other, SourceNode):
            return False

        return (self.sourceType == other.sourceType
                and self.sourceName == other.sourceName)

    def __repr__(self) -> str:
        return self.sourceName


class CodeNode:
    def __init__(self, class_body=None, inheritance_declare=None) -> None:
        self.class_body = class_body
        self.inheritance_declare = inheritance_declare

    def __hash__(self) -> int:
        return hash(self.class_body) ^ hash(self.inheritance_declare)

    def __eq__(self, other):
        if not isinstance(other, CodeNode):
            return False

        return (self.class_body == other.class_body
                and self.inheritance_declare == other.inheritance_declare)

    def __repr__(self) -> str:
        return self.class_body


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, TypeNode):
            return {"name": obj.name, "classifier": obj.classifier.name, "sourceName": obj.sourceName, "sourceType": obj.sourceType.name}
        if isinstance(obj, EdgeNode):
            caller = json.loads(json.dumps(obj.caller, cls=CustomEncoder))
            callee = json.loads(json.dumps(obj.callee, cls=CustomEncoder))
            return {"caller": caller, "callee": callee, "refType": obj.refType.name}

        return json.JSONEncoder.default(self, obj)


class TypeDependencyDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        json.JSONDecoder.__init__(self, object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, dct):
        if 'name' in dct and 'classifier' in dct and 'sourceName' in dct and 'sourceType' in dct:
            return TypeNode(dct['name'], TypeClassifier[dct['classifier']], dct['sourceName'], SourceType[dct['sourceType']])
        if 'caller' in dct and 'callee' in dct and 'refType' in dct:
            return EdgeNode(dct['caller'], dct['callee'], RefType[dct['refType']])
        return dct


class EdgeNode:
    def __init__(self, caller: TypeNode, callee: TypeNode, refType: RefType) -> None:
        self.callee = callee
        self.caller = caller
        self.refType = refType

    def __hash__(self) -> int:
        return hash(self.caller) ^ hash(self.callee) ^ hash(self.refType)

    def __eq__(self, other):
        if not isinstance(other, TypeNode):
            return False

        return (self.caller == other.sourceName
                and self.callee == other.sourceType
                and self.refType == other.name)

    def __str__(self) -> str:
        return f'{self.caller} -> {self.callee}'


if __name__ == '__main__':
    tc = TypeClassifier.parseval('enum class')
    print(tc)
    tc = TypeClassifier.parseval('enum')
    print(tc)
    st = SourceType.parseval('.c++')
    print(st)
    src = SourceNode('foo.h')
    print(src)

    abc = TypeNode('abc', TypeClassifier.ENUM, 'foo', SourceType.HEADER)
    abc_json = json.dumps(abc, cls=CustomEncoder)
    resurrected_abc = json.loads(abc_json, cls=TypeDependencyDecoder)
    print(f'original: {abc}\njson: {abc_json}\nresurrected: {resurrected_abc}')

    foo = TypeNode('Foo', TypeClassifier.CLASS, 'bar', SourceType.CPP)
    edge = EdgeNode(foo, abc, RefType.COMPOSITION)
    edge_json = json.dumps(edge, cls=CustomEncoder)
    resurrected_edge = json.loads(edge_json, cls=TypeDependencyDecoder)
    print(f'original: {edge}\njson: {edge_json}\n resurrected: {resurrected_edge}')
