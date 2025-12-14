import { Box, Button, Chip, Divider, Grid2 as Grid, IconButton, InputAdornment, Paper, Stack, Tooltip, Typography, TextField, FormControl, Select, MenuItem, Autocomplete } from "@mui/material"
import ClearIcon from '@mui/icons-material/Clear';
import SearchIcon from '@mui/icons-material/Search';
import FilterAltOutlinedIcon from '@mui/icons-material/FilterAltOutlined';
import LayersOutlinedIcon from '@mui/icons-material/LayersOutlined';
import LanOutlinedIcon from '@mui/icons-material/LanOutlined';
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

  const totalPods = data.length

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

  const containerSummary = useMemo(() => {
    return filteredData.reduce((acc, item) => {
      const count = getNestedValue(item, 'spec.containers.length') || 0;
      if (count <= 1) acc.single += 1;
      if (count > 1) acc.multiple += 1;
      return acc;
    }, { single: 0, multiple: 0 });
  }, [filteredData]);

  const activeFilters = useMemo(() => {
    const chips = [];
    if (searchTerm) chips.push({ label: `Search: ${searchTerm}`, key: 'search' });
    if (selectedNamespace) chips.push({ label: `Namespace: ${selectedNamespace}`, key: 'namespace' });
    if (selectedNode !== "all") chips.push({ label: `Node: ${selectedNode}`, key: 'node' });
    if (containerFilter !== "all") chips.push({ label: containerFilter === "single" ? "Single container" : "Multiple containers", key: 'container' });
    return chips;
  }, [searchTerm, selectedNamespace, selectedNode, containerFilter]);

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
            <Grid container spacing={2} sx={{ mt: 1, mb: 1 }}>
              <Grid xs={12} md={4}>
                <Box sx={{ p: 2.5, borderRadius: 2, bgcolor: 'grey.100', border: '1px solid', borderColor: 'divider' }}>
                  <Stack direction="row" spacing={1} alignItems="center" sx={{ color: 'text.secondary', mb: 0.5 }}>
                    <FilterAltOutlinedIcon fontSize="small" />
                    <Typography variant="body2">Filtered Pods</Typography>
                  </Stack>
                  <Typography variant="h5" sx={{ fontWeight: 700 }}>{filteredData.length}</Typography>
                  <Typography variant="caption" color="text.secondary">of {totalPods} total pods</Typography>
                </Box>
              </Grid>
              <Grid xs={12} md={4}>
                <Box sx={{ p: 2.5, borderRadius: 2, bgcolor: 'grey.100', border: '1px solid', borderColor: 'divider' }}>
                  <Stack direction="row" spacing={1} alignItems="center" sx={{ color: 'text.secondary', mb: 0.5 }}>
                    <LanOutlinedIcon fontSize="small" />
                    <Typography variant="body2">Namespaces</Typography>
                  </Stack>
                  <Typography variant="h5" sx={{ fontWeight: 700 }}>{namespaceOptions.length || 0}</Typography>
                  <Typography variant="caption" color="text.secondary">unique namespaces detected</Typography>
                </Box>
              </Grid>
              <Grid xs={12} md={4}>
                <Box sx={{ p: 2.5, borderRadius: 2, bgcolor: 'grey.100', border: '1px solid', borderColor: 'divider' }}>
                  <Stack direction="row" spacing={1} alignItems="center" sx={{ color: 'text.secondary', mb: 0.5 }}>
                    <LayersOutlinedIcon fontSize="small" />
                    <Typography variant="body2">Containers</Typography>
                  </Stack>
                  <Typography variant="h5" sx={{ fontWeight: 700 }}>{containerSummary.single} single / {containerSummary.multiple} multi</Typography>
                  <Typography variant="caption" color="text.secondary">within filtered pods</Typography>
                </Box>
              </Grid>
            </Grid>
            <Box sx={{ mt: 2, mb: 2, p: 2, borderRadius: 2, border: '1px solid', borderColor: 'divider', bgcolor: 'grey.50' }}>
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
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <SearchIcon fontSize="small" color="action" />
                      </InputAdornment>
                    )
                  }}
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
                  variant="contained"
                  color="secondary"
                  startIcon={<ClearIcon />}
                  onClick={clearFilters}
                  size="small"
                  disabled={searchTerm === "" && !selectedNamespace && selectedNode === "all" && containerFilter === "all"}
                >
                  Clear Filters
                </Button>
              </Box>
              {!!activeFilters.length && (
                <Stack direction="row" flexWrap="wrap" spacing={1} useFlexGap sx={{ mt: 2 }}>
                  {activeFilters.map(({ label, key }) => (
                    <Chip
                      key={key}
                      label={label}
                      size="small"
                      onDelete={clearFilters}
                      color="primary"
                      variant="outlined"
                    />
                  ))}
                </Stack>
              )}
              <Divider sx={{ my: 2 }} />
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