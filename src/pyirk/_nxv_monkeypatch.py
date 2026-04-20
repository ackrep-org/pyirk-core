import networkx as nx

# monkey-patch workaround because nxv currently is broken for new networkx releases

if not hasattr(nx, "OrderedGraph"):
    nx.OrderedGraph = nx.Graph
    nx.OrderedDiGraph = nx.DiGraph
    nx.OrderedMultiGraph = nx.MultiGraph
    nx.OrderedMultiDiGraph = nx.MultiDiGraph
