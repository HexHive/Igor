from logging import root
import os
import typing
import igraph
import networkx
import graphviz

class DCFG:
    """ Base class for DCFG 
    """
    def __init__(self, trace :str) -> None:
        """ Init from a trace file

        :param trace: trace file
        :return: None
        """
        self._trace_path = os.path.abspath(trace)
        self._trace_name = os.path.basename(self._trace_path)
        self._trace_list = None

        self._node_head = None
        self._node_tail = None

        #Key: address (int rather than hex-str) as node unique identifier in NetworkX [int]
        #Val: hit count [int]
        self._node_hit = {}

        #Key: (node_id_front, node_id_next) as edge [tuple]
        #Val: hit count [int]
        self._edge_hit = {}

        self.DCFG_RAW = None

    @staticmethod
    def trace_line_interpreter(l :bytes) -> int :
        """ Trace line in "rb" file mode => Int address

        e.g. b'0x00047c308' => 4702984
        """
        return int(l.decode('utf-8','ignore').rstrip(), 16)

    @staticmethod
    def set_hit_count(d :dict, x :typing.Any) -> None :
        """ Use a dict to record hit count

        The dict:
            Key: Any hashable Python object which can be used as a key in a Python dictionary.
            Val: hit count (1 hit => counter+=1)
        [Higher performance in dict-key-check](https://cloud.tencent.com/developer/article/1820102?ivk_sa=1024320u)
        """
        if x in d:
            d[x] += 1
        else:
            d[x] = 1  

    def traverse_trace_file(self) -> None :
        """ Extract DCFG data from a trace record file
        """
        with open(self._trace_path, mode="rb") as f:
            self._trace_list = f.readlines()
        
        self._node_head = self.trace_line_interpreter(self._trace_list[0])
        self._node_tail = self.trace_line_interpreter(self._trace_list[-1])

        lastN = self._node_head
        self.set_hit_count(self._node_hit, lastN)

        for i in range(1, len(self._trace_list)):
            thisN = self.trace_line_interpreter(self._trace_list[i])
            #Current directed edge: (lastN, thisN)
            self.set_hit_count(self._edge_hit, (lastN,thisN))
            lastN = thisN
            self.set_hit_count(self._node_hit, lastN)

    def is_dense(self) -> typing.Union[None,bool] :
        """ Determining whether the DCFG (i.e. `self.DCFG_RAW`) is sparse or dense

        `Borgwardt, Karsten, et al. "Graph kernels: State-of-the-art and future challenges." arXiv preprint arXiv:2011.03854 (2020).`
            The only decision a user needs to take here is to check the density of
            the graphs data set beforehand. We purposefully leave the definition of 
            what constitutes a dense graph open—a straightforward threshold would be 
            to define graphs with a density of > 0.5 to be dense, as opposed to sparse.

        `https://en.wikipedia.org/wiki/Dense_graph`
            for directed simple graphs, the graph density is defined as $D=\frac{|E|}{|V|(|V|-1)}$
        """
        card_E = len(self._edge_hit)
        card_V = len(self._node_hit)
        if (0 == card_E):
            return None
        else:
            return (card_E/(card_V*(card_V - 1)) > 0.5)


class DCFG_NX(DCFG):
    """ DCFG by NetworkX

    https://networkx.org/documentation/stable/reference/introduction.html
    """  
    def construct_dcfg(self) -> None :
        """ Construct DCFG with 2 attributes for node and 1 for edge

        One raw value of the attributes for node is used as unique 
        identifier for node in NetworX, too.
        """
        self.traverse_trace_file()
        self.DCFG_RAW = networkx.DiGraph()

        for vtx in self._node_hit:
            self.DCFG_RAW.add_node(vtx, addr=vtx, hit=self._node_hit[vtx])

        for edg in self._edge_hit:
            self.DCFG_RAW.add_edge(edg[0], edg[1], hit=self._edge_hit[edg])

    def return_dcfg(self) -> networkx.DiGraph :
        """ Provide DCFG for outside request.
        """
        return self.DCFG_RAW

    def _return_ego_dcfg(self, NID :int, RAD :int, ALT :typing.Union[str,None]) -> networkx.DiGraph :
        """ Provide DCFG in Ego graph.

        1. WHAT IS `Ego Graph`
        http://olizardo.bol.ucla.edu/classes/soc-111/lessons-winter-2022/5-lesson-egonet-metrics.html
        Ego graphs are also referred to as centered graphs. Ego graphs are useful for 
        representing egocentric networks. An ego graph is the graph of all nodes that 
        are less than a certain distance from the center node.

        2. Params
            2.1 NID
                Node Identifier for center node.
                Center node will be included in ego graph.
                Node, edge, and graph attributes are copied to the returned subgraph.
            2.2 RAD
                Include all neighbors of distance<=`RAD` from node `NID`.
                Both in- and out-neighbors of directed graphs will be included.
            2.3 ALT
                Use specified edge data key as distance. For example, 
                setting `ALT='weight'` will use the edge weight to 
                measure the distance from the node `NID`.
        """
        return networkx.ego_graph(self.DCFG_RAW, NID, 
                                  radius = RAD, 
                                  center = True,
                                  undirected = True,
                                  distance = ALT)

    def return_tail_ego_dcfg(self, RAD :int) -> networkx.DiGraph :
        """ Provide DCFG in Ego graph with the tail of trace file as center.

        A wrapper of return_ego_dcfg with `NID=self._node_tail`, `ALT=None`
        """
        return self._return_ego_dcfg(self._node_tail, RAD, None)
    
    def render_dcfg(self) -> None :
        """ Render DCFG by methods from NetworkX. 

        TODO: doc & implementation
        # Goto prototype/test.ipynb for more...
        """
        pos_layout = \
            networkx.nx_agraph.graphviz_layout(
                self.DCFG_RAW,
                prog = "fdp",
                root = None
            )


class DCFG_GV(DCFG):
    """ DCFG by Graphviz

    https://graphviz.readthedocs.io/en/stable/api.html#api-reference
    """
    def construct_dcfg(self) -> None :
        """ Construct DCFG with head and tail colored.
        """
        self.traverse_trace_file()
        self.DCFG_RAW = graphviz.Digraph()

        for vtx in self._node_hit:
            self.DCFG_RAW.node(str(vtx), hit=str(self._node_hit[vtx]))

        for edg in self._edge_hit:
            self.DCFG_RAW.edge(str(edg[0]), str(edg[1]), label=str(self._edge_hit[edg]))

        self.DCFG_RAW.node(str(self._node_head), color="green", style="filled", fillcolor="green")
        self.DCFG_RAW.node(str(self._node_tail), color="red",   style="filled", fillcolor="red"  )
    
    def return_dcfg(self) -> graphviz.Digraph :
        """ Provide DCFG for outside request.
        """
        return self.DCFG_RAW

    def render_dcfg(self, suffix :str ="_GraphvizGen", dirname :str =None) -> None :
        """ Render DCFG to png by engines from Graphviz. 

        Irritatingly slow but attractively beautiful...

        :param suffix: The suffix attached to the trace file
        :param dir: (Sub)directory for graphviz file saving and rendering.
                    Will place it alongside the trace file by default.
        """
        self.DCFG_RAW.render(filename  = self._trace_name + suffix,
                             directory = dirname,
                             cleanup = True, 
                             format  = "png",
                             engine  = "dot")


class DCFG_IG(DCFG):
    """ DCFG by igraph

    https://igraph.org/python/api/latest/

    This class can also be designed by inheriting `DCFG_NX`, 
    but we do not do so to avoid the impact of 
    `networkx.DiGraph` intermediates on system overhead.
    """
    def construct_dcfg(self) -> None :
        """ Construct DCFG with 0 additional attribute for node and 1 for edge

        In `igraph.Graph`, according to [this](https://igraph.org/python/api/latest/igraph.Graph.html#from_networkx), 
        ids of vertices are from 0 up (as standard in igraph). And `igraph.Graph` does NOT provide any interface to
        intervene in this ID-allocation-mode for its users in contrast to `NetworkX`. 

        However, according to [this](https://igraph.org/python/api/latest/igraph.Graph.html#add_vertex), 
        if a graph has `name` as a vertex attribute, it allows one to refer to vertices by their names 
        in most places where igraph expects a vertex ID.

        We do not add additional attribute `hit` for nodes to avoid the potential for 
        multi-labels to interfere with the graph kernel methods, because
        [BorgwardtLab/GraphKernels](https://github.com/BorgwardtLab/GraphKernels/tree/master/Tutorial)
        indicates that kernel algorithms from here does not provide params for choosing which label 
        to load in contrast to `GraKeL`.
        """
        self.traverse_trace_file()
        self.DCFG_RAW = igraph.Graph(directed = True)

        self._vtxs = [str(addr) for addr in self._node_hit]
        self.DCFG_RAW.add_vertices(self._vtxs)

        edgs = []
        tags = {"hit":[]}
        for edg in self._edge_hit:
            edgs.append((str(edg[0]) , str(edg[1])))
            tags["hit"].append(self._edge_hit[edg])
        self.DCFG_RAW.add_edges(edgs, tags)

    def return_dcfg(self) -> igraph.Graph :
        """ Provide DCFG for outside request.
        """
        return self.DCFG_RAW

    def _return_ego_dcfg(self, VID :int, RAD :int) -> igraph.Graph :
        """ Provide DCFG in Ego graph.

        ### WHAT IS `Ego Graph`

        http://olizardo.bol.ucla.edu/classes/soc-111/lessons-winter-2022/5-lesson-egonet-metrics.html
        Ego graphs are also referred to as centered graphs. Ego graphs are useful for 
        representing egocentric networks. An ego graph is the graph of all nodes that 
        are less than a certain distance from the center node.

        ### Ways to create ego-graph in python-igraph

        https://igraph-help.nongnu.narkive.com/xKp11GRa/igraph-things-about-ways-to-create-ego-graph-in-python-igraph
        Using `graph.neighborhood()` with the appropriate parameterization, in
        combination with `graph.induced_subgraph()`.
            
        ### Parameters
            `VID`
                Vertex ID for center vertex.
                Center vertex will be included in ego graph.
                All attributes are copied to the returned subgraph.
            `RAD`
                Include all neighbors of distance<=`RAD` from vertex `VID`.
                Both in- and out-neighbors of directed graphs will be included.
        """
        #ids of vertices are from 0 up (as standard in igraph)
        assert (VID in range(len(self._node_hit))) , "Invalid Vertex ID"
        #https://igraph.org/python/api/latest/igraph._igraph.GraphBase.html#neighborhood
        sub_vertices_lst = \
            self.DCFG_RAW.neighborhood(
                vertices = VID,
                order = RAD,
                mode = "all",
                mindist = 0
            )
        #https://igraph.org/python/api/latest/igraph._igraph.GraphBase.html#induced_subgraph
        return self.DCFG_RAW.induced_subgraph(sub_vertices_lst, implementation = "auto")

    def _addr2vid(self, addr :int) -> int :
        """ Get true vertex id in `self.DCFG_RAW`-an `igraph.Graph`, by vertex name-`str(addr)`
        """
        return self._vtxs.index(str(addr))

    def return_tail_ego_dcfg(self, RAD :int) -> igraph.Graph :
        """ Provide DCFG in Ego graph with the tail of trace file as center.

        A wrapper of return_ego_dcfg with `VID=str(self._node_tail)`
        """
        return self._return_ego_dcfg(self._addr2vid(self._node_tail), RAD)
    
    def render_dcfg(self) -> None :
        """ Render DCFG by methods from NetworkX. 

        TODO: doc & implementation
        """
        #Output of the statement below looks very ugly...
        igraph.plot(self.DCFG_RAW, "DCFG_RAW.svg", layout = self.DCFG_RAW.layout_lgl())


if __name__ == "__main__":
    dcfg_test = DCFG_IG(r"./prototype/testcase/AAH017_tif_dirwrite_c_2104_8ea_id:000143-sig:06-src:000005-op:flip1-pos:236_drw_concise")
    dcfg_test.construct_dcfg()
    G_all = dcfg_test.return_dcfg()
    G_sub = dcfg_test.return_tail_ego_dcfg(3)
    #https://igraph.org/python/api/latest/igraph.Graph.html#summary
    print(G_all.summary(verbosity = 0, width = None))
    print(G_sub.summary(verbosity = 0, width = None))
