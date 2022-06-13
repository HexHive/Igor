import typing
import numpy
import networkx
import grakel

class GKA:
    """ Base class for GKA (Graph Kernel Algorithm)
    """
    def __init__(self) -> None :
        self.graph_lst = []
        self.graph_mat = None
    
    def add_dcfg(self, g) -> None :
        """ Add a DCFG to internal graph list (`self.graph_lst`)
        """
        self.graph_lst.append(g)

    def del_dcfg(self, g) -> None :
        """ Remove a DCFG from internal graph list (`self.graph_lst)`
        """
        if g in self.graph_lst:
            self.graph_lst.remove(g)

    def get_matrix(self) -> typing.Optional[numpy.ndarray] :
        """ return the similarity matrix
        """
        return self.graph_mat


class GKA_GraKeL(GKA):
    """ Use graph kernel algorithms from GraKeL

    https://ysig.github.io/GraKeL/0.1a8/index.html

    `Siglidis, Giannis, et al. "GraKeL: A Graph Kernel Library in Python." J. Mach. Learn. Res. 21.54 (2020): 1-5.`
        In GraKeL, all graph kernels are required to inherit the `Kernel` class which inherits from
        the scikit-learn's `TransformerMixin` class and implements the following four methods:
            
            1. `fit`: 
                Extracts kernel dependent features from an input graph collection.
            
            2. `fit transform`: 
                Fits and calculates the kernel matrix of an input graph collection.
            
            3. `transform`: 
                Calculates the kernel matrix between a new collection of graphs 
                and the one given as input to `fit`.
            
            4. `diagonal`: 
                Returns the self-kernel values of all the graphs given as input to `fit` 
                along with those given as input to `transform`, provided that this method 
                has been called. This method is used for normalizing kernel matrices.
        
        All kernels are unified under a submodule named `kernels`. They are all wrapped in a
        general class called `GraphKernel` which also inherits from scikit-learn's `TransformerMixin`.

        Besides providing a unified interface, it is also useful for applying other operations such
        as the the Nystrom method, while it also facilitates the use of kernel frameworks that are
        currently supported by GraKeL. Frameworks like the Weisfeiler Lehman algorithm (Shervashidze
        et al., 2011) can use any instance of the `Kernel` class as their base kernel.

        The input is required to be an `Iterable` collection of graph representations. Each graph
        can be either an `Iterable` consisting of a graph representation object (e. g., adjacency
        matrix, edge dictionary), vertex attributes and edge attributes or a `Graph` class instance.

        The vertex and edge attributes can be discrete (a.k.a. vertex and edge labels in the literature
        of graph kernels) or continuous-valued feature vectors. Note that some kernels cannot
        handle vector attributes, while others assume unlabeled graphs. 
        
        Furthermore, through its `datasets` submodule, GraKeL facilitates the application of graph kernels 
        to several popular graph classification datasets contained in a public repository (Kersting et al., 2016).
    """
    def __init__(self, isVerbose :bool =False, setJoblib :typing.Optional[int] =None) -> None :
        """ Constructor

        [Reference](https://ysig.github.io/GraKeL/0.1a8/generated/grakel.Kernel.html#grakel-kernel)

        `isVerbose`<->`self._isVerbose`<->`verbose`:
            Define if messages will be printed on stdout.
        `setJoblib`<->`self._setJoblib`<->`n_jobs`:
            Defines the number of jobs of a `joblib.Parallel` objects 
            needed for parallelization or `None` for direct execution.
        """
        super().__init__()
        self._isVerbose = isVerbose
        self._setJoblib = setJoblib
    
    def add_dcfg(self, nxg :networkx.DiGraph) -> None :
        """ Add a DCFG (DiGraph from NetworkX) to the internal graph list
        """
        self.graph_lst.append(nxg)
    
    def del_dcfg(self, nxg :networkx.DiGraph) -> None :
        """ Remove a DCFG (DiGraph from NetworkX) from the internal graph list
        """
        self.graph_lst.remove(nxg)

    def _fit_graph_list(self) -> None :
        """ Transform `graph_lst` into a container, i.e., `_graph_container`, suitable for GraKeL
        """
        self._graph_container = \
            grakel.graph_from_networkx(self.graph_lst, 
                                       node_labels_tag = "addr",
                                       edge_labels_tag = "hit")
    
    def apply_WL_Subtree_Kernel(self) -> None :
        """ Use Weisfeiler-Lehman Subtree Kernel to calculate the similarity matrix

        [Tutorial](https://ysig.github.io/GraKeL/0.1a8/kernels/weisfeiler_lehman.html)
        [API Reference](https://ysig.github.io/GraKeL/0.1a8/generated/grakel.WeisfeilerLehman.html#grakel.WeisfeilerLehman)
        """
        self._fit_graph_list()
        self.graph_mat = \
            grakel.WeisfeilerLehman(
                n_iter = 1, 
                base_graph_kernel = grakel.VertexHistogram, 
                normalize = True,
                verbose = self._isVerbose,
                n_jobs  = self._setJoblib
            ).fit_transform(self._graph_container)
    
    def apply_WL_Optimal_Assignment_Kernel(self) -> None :
        """ Use Weisfeiler-Lehman Optimal Assignment Kernel to calculate the similarity matrix

        The Weisfeiler-Lehman optimal assignment kernel capitalizes on the theory of 
        valid assignment kernels to improve the performance of the Weisfeiler-Lehman subtree kernel

        [Tutorial](https://ysig.github.io/GraKeL/0.1a8/kernels/weisfeiler_lehman_optimal_assignment.html)
        [API Reference](https://ysig.github.io/GraKeL/0.1a8/generated/grakel.WeisfeilerLehmanOptimalAssignment.html#grakel.WeisfeilerLehmanOptimalAssignment)
        """
        self._fit_graph_list()
        self.graph_mat = \
            grakel.WeisfeilerLehmanOptimalAssignment(
                n_iter = 1,
                sparse = False,
                normalize = True,
                verbose = self._isVerbose,
                n_jobs  = self._setJoblib
            ).fit_transform(self._graph_container)

    def apply_Vertex_Histogram_Kernel(self) -> None :
        """ Use Vertex Histogram Kernel to calculate the similarity matrix
        [Tutorial](https://ysig.github.io/GraKeL/0.1a8/kernels/vertex_histogram.html)
        [API Reference](https://ysig.github.io/GraKeL/0.1a8/generated/grakel.VertexHistogram.html#grakel.VertexHistogram)
        """
        pass

    def apply_Edge_Histogram_Kernel(self) -> None :
        """ Use Edge Histogram Kernel to calculate the similarity matrix
        [Tutorial](https://ysig.github.io/GraKeL/0.1a8/kernels/edge_histogram.html)
        [API Reference](https://ysig.github.io/GraKeL/0.1a8/generated/grakel.EdgeHistogram.html)
        """
        pass

    def apply_Shortest_Path_Kernel(self) -> None :
        """ Use Shortest Path Kernel to calculate the similarity matrix
        [Tutorial](https://ysig.github.io/GraKeL/0.1a8/kernels/shortest_path.html)
        [API Reference](https://ysig.github.io/GraKeL/0.1a8/generated/grakel.ShortestPath.html#grakel.ShortestPath)
        """
        pass

    def apply_Random_Walk_Kernel(self) -> None :
        """ Use Random Walk Kernel to calculate the similarity matrix
        [Tutorial](https://ysig.github.io/GraKeL/0.1a8/kernels/random_walk.html)
        [API Reference](https://ysig.github.io/GraKeL/0.1a8/generated/grakel.RandomWalkLabeled.html#grakel.RandomWalkLabeled)
        """
        pass

    def apply_Multiscale_Laplacian_Kernel(self) -> None :
        """ Use Multiscale Laplacian Kernel to calculate the similarity matrix
        [Tutorial](https://ysig.github.io/GraKeL/0.1a8/kernels/multiscale_laplacian.html)
        [API Reference](https://ysig.github.io/GraKeL/0.1a8/generated/grakel.MultiscaleLaplacian.html#grakel.MultiscaleLaplacian)
        """
        pass

    def apply_Neighborhood_Subgraph_Pairwise_Distance_Kernel(self) -> None :
        """ Use Neighborhood Subgraph Pairwise Distance Kernel to calculate the similarity matrix
        [Tutorial](https://ysig.github.io/GraKeL/0.1a8/kernels/neighborhood_subgraph_pairwise_distance.html)
        [API Reference](https://ysig.github.io/GraKeL/0.1a8/generated/grakel.NeighborhoodSubgraphPairwiseDistance.html#grakel.NeighborhoodSubgraphPairwiseDistance)
        """
        pass
    
    def apply_kernel_template(self) -> None :
        """ Use ? Kernel to calculate the similarity matrix
        [Tutorial](?)
        [API Reference](?)
        """
        pass


if __name__ == "__main__":
    pass