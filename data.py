from make_json_serializable import monkey_patching
monkey_patching()

from networkx.readwrite import json_graph
from neo4j import GraphDatabase
from pypher import Pypher, __


def write_graph_to_neo4j(graph):
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "luo0322"))
    g_data = json_graph.node_link_data(graph.graph)
    with driver.session() as session:
        for node in g_data["nodes"]:
            node["labels"] = node["type"]
            node["node_id"] = node["id"]
            del(node["type"])
            del(node["id"])
            del(node["value"])
            p = Pypher()
            p.Merge.node('node', **node)
            session.run(str(p), **p.bound_params)

        for link in g_data["links"]:
            p = Pypher()
            p.Match(__.node('source', node_id=link["source"]), __.node('target', node_id=link["target"]))
            p.Merge.node('source').relationship(direction="out", labels=link["relation"]).node('target')
            session.run(str(p), **p.bound_params)
