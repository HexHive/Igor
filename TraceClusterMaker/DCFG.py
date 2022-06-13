import os
import typing
import networkx

class DCFG:
    """ Base class for DCFG (Dynamic Control-Flow Graph)
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

        #Key: address (int rather than hex-str) for identifying a node [int]
        #Val: hit count [int]
        self._node_hit = {}

        #Key: (node_id_front, node_id_next) for identifying a edge [tuple]
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
        [Higher performance in dict-has-key-check](https://stackoverflow.com/questions/1323410/should-i-use-has-key-or-in-on-python-dicts)
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

    def is_dense(self) -> typing.Optional[bool] :
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


if __name__ == "__main__":
    pass