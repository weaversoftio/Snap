import { Box, Button, Grid2 as Grid, IconButton, Paper, Tooltip, Typography, TextField, FormControl, Select, MenuItem, Autocomplete } from "@mui/material"
import ClearIcon from '@mui/icons-material/Clear';
import { useEffect, useMemo, useState } from "react";
import { podsApi } from "../../api/podsApi";
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useSelector } from "react-redux";
import BeautifulAnalysisResults from "../common/BeautifulAnalysisResults";
import TableComponent from "./PodsTable";
import { Loading } from "../common/loading";
import { CustomerContainer } from "../common/CustomContainer";

const PodsScreen = ({ classes }) => {
  const { selectedCluster = null } = useSelector(state => state.cluster)

  const [loading, setLoading] = useState(false)
  const [data, setData] = useState([])
  const [currentPod, setCurrentPod] = useState(null)
  const [rowsPerPage, setRowsPerPage] = useState(5)
  const [page, setPage] = useState(0)
  const [searchTerm, setSearchTerm] = useState("")
  const [selectedNamespace, setSelectedNamespace] = useState(null)
  const [selectedNode, setSelectedNode] = useState("all")
  const [containerFilter, setContainerFilter] = useState("all")

  const tableHeaders = [
    { name: "", key: "" },
    { name: "Name", key: "metadata.name" },
    { name: "Namespace", key: "metadata.namespace" },
    { name: "Nodename", key: "spec.nodeName" },
    { name: "No. of Containers", key: "spec.containers.length" },
    {
      name: "Actions", key: "", action: (data) => (
        <Tooltip title="Inspect Pod">
          <IconButton onClick={() => handleShowPods(data?.metadata?.name)}><VisibilityIcon /></IconButton>
        </Tooltip>
      )
    },
  ]

  const nestedTableHeaders = [
    { name: "Name", key: "container_name" },
    { name: "Image", key: "image_name" },
    { name: "Action", key: "" }
  ]

  const handleShowPods = (name) => {
    const pod = filteredData.find((item) => item?.metadata?.name === name) || data.find((item) => item?.metadata?.name === name)
    setCurrentPod(pod)
  }

  const handleRowsPerPageChange = (event) => {
    setRowsPerPage(+event.target.value);
    setPage(0);
  };

  const handlePageChange = (event, newPage) => {
    setPage(newPage);
  };

  const handleGetPods = async () => {
    try {
      setLoading(true)
      const result = await podsApi.getList()
      const data = JSON.parse(result.pods)
      // console.log({ result })
      // const data = JSON.parse(podsData.pods)
      setData(data.items)
    } catch (error) {
      console.error("Pods error ", error)
    }
    setLoading(false)

  }

  useEffect(() => {
    handleGetPods()
  }, [])

  const getNestedValue = (obj, path) => {
    return path.split('.').reduce((acc, key) => acc && acc[key], obj);
  }

  const filteredData = useMemo(() => {
    return data.filter(item => {
      const searchFields = [
        getNestedValue(item, 'metadata.name'),
        getNestedValue(item, 'metadata.namespace'),
        getNestedValue(item, 'spec.nodeName')
      ];
      const matchesSearch = searchFields.some(field =>
        String(field).toLowerCase().includes(searchTerm.toLowerCase())
      );
      const matchesNamespace = !selectedNamespace || getNestedValue(item, 'metadata.namespace') === selectedNamespace;
      const matchesNode = selectedNode === "all" || getNestedValue(item, 'spec.nodeName') === selectedNode;
      const containerCount = getNestedValue(item, 'spec.containers.length') || 0;
      const matchesContainer = containerFilter === "all" 
        ? true 
        : containerFilter === "single" 
          ? containerCount === 1 
          : containerCount > 1;

      return matchesSearch && matchesNamespace && matchesNode && matchesContainer;
    });
  }, [data, searchTerm, selectedNamespace, selectedNode, containerFilter]);

  const namespaceOptions = useMemo(() => {
    return Array.from(new Set(data.map(item => getNestedValue(item, 'metadata.namespace')).filter(Boolean)))
  }, [data]);

  const nodeOptions = useMemo(() => {
    return Array.from(new Set(data.map(item => getNestedValue(item, 'spec.nodeName')).filter(Boolean)))
  }, [data]);

  const clearFilters = () => {
    setSearchTerm("")
    setSelectedNamespace(null)
    setSelectedNode("all")
    setContainerFilter("all")
    setPage(0)
  }

  useEffect(() => {
    setPage(0)
  }, [searchTerm, selectedNamespace, selectedNode, containerFilter])

  const renderDialog = () => {
    if (!currentPod) return
    const { metadata = null } = currentPod || {}
    const { name = "" } = metadata

    return (
      <BeautifulAnalysisResults
        data={currentPod}
        open={!!name}
        onClose={() => setCurrentPod(null)}
        title={`Pod Analysis: ${name}`}
      />
    )
  }

  if (!selectedCluster) return (
    <Box height={"100%"} width={"100%"} textAlign={"center"}>
      <Typography>Add Cluster To Get Start</Typography>
    </Box>
  )

  return (
    <CustomerContainer title="Pods" subtitle="List of Pods in the cluster">
      {loading ? <Loading /> : (
        <>
          <Paper elevation={0} sx={{ px: 3, py: 1, bgcolor: 'background.paper', borderRadius: 2 }}>
            {renderDialog()}
            <Box sx={{ mt: 2, mb: 2 }}>
              <Typography variant="h6" gutterBottom sx={{ mb: 2 }}>
                Search & Filters
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 2 }}>
                <TextField
                  sx={{ width: '300px', minWidth: '200px' }}
                  size="small"
                  placeholder="Search by name, namespace, or node"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
                <Autocomplete
                  sx={{ minWidth: 180 }}
                  size="small"
                  options={namespaceOptions}
                  value={selectedNamespace}
                  onChange={(event, newValue) => setSelectedNamespace(newValue)}
                  renderInput={(params) => (
                    <TextField {...params} placeholder="All Namespaces" />
                  )}
                  freeSolo
                  selectOnFocus
                  clearOnBlur
                  handleHomeEndKeys
                />
                <FormControl sx={{ minWidth: 180 }} size="small">
                  <Select
                    value={selectedNode}
                    onChange={(e) => setSelectedNode(e.target.value)}
                    displayEmpty
                  >
                    <MenuItem value="all">All Nodes</MenuItem>
                    {nodeOptions.map(node => (
                      <MenuItem key={node} value={node}>{node}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <FormControl sx={{ minWidth: 150 }} size="small">
                  <Select
                    value={containerFilter}
                    onChange={(e) => setContainerFilter(e.target.value)}
                    displayEmpty
                  >
                    <MenuItem value="all">All Containers</MenuItem>
                    <MenuItem value="single">Single Container</MenuItem>
                    <MenuItem value="multiple">Multiple Containers</MenuItem>
                  </Select>
                </FormControl>
                <Button
                  variant="outlined"
                  startIcon={<ClearIcon />}
                  onClick={clearFilters}
                  size="small"
                  disabled={searchTerm === "" && !selectedNamespace && selectedNode === "all" && containerFilter === "all"}
                >
                  Clear Filters
                </Button>
              </Box>
              {filteredData.length !== data.length && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  Showing {filteredData.length} of {data.length} pods
                </Typography>
              )}
            </Box>
            <TableComponent
              classes={classes}
              data={filteredData}
              tableHeaders={tableHeaders}
              nestedTableHeaders={nestedTableHeaders}
              total={filteredData.length}
              rowsPerPage={rowsPerPage}
              page={page}
              handleRowsPerPageChange={handleRowsPerPageChange}
              handlePageChange={handlePageChange}
            />
          </Paper>
        </>

      )

      }
    </CustomerContainer>
  )
}

export default PodsScreen;