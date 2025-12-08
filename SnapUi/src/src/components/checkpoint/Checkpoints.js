import { Box, Button, CircularProgress, FormControl, Grid2 as Grid, MenuItem, Select, TextField, Typography, Card, Paper } from "@mui/material"
import ClearIcon from '@mui/icons-material/Clear';
import { useEffect, useMemo, useState } from "react";
import TableComponent from "../common/Table";
import { useSnackbar } from 'notistack';
import { checkpointApi } from "../../api/checkpointApi";
import { SimpleDialog } from "../common/SimpleDialog";
import ReactJson from 'react-json-view';
import BeautifulAnalysisResults from "../common/BeautifulAnalysisResults";
import Stack from '@mui/material/Stack';
import IconButton from '@mui/material/IconButton';
import PlayArrowRoundedIcon from '@mui/icons-material/PlayArrowRounded';
import TextSnippetRoundedIcon from '@mui/icons-material/TextSnippetRounded';
import Tooltip from '@mui/material/Tooltip';
import FileUploadIcon from '@mui/icons-material/FileUpload';
import DownloadIcon from '@mui/icons-material/Download';
import { useDispatch, useSelector } from "react-redux";
import DialogComponent from "../common/Dialog";
import AddCircleIcon from '@mui/icons-material/AddCircle';
import { registryActions } from "../../features/registry/registrySlice";
import { registryApi } from "../../api/registryApi";
import { Loading } from "../common/loading";
import { CustomerContainer } from "../common/CustomContainer";

const CheckpointsScreen = ({ classes }) => {
  const dispatch = useDispatch()
  const { enqueueSnackbar } = useSnackbar();
  const { list: registryList = [], } = useSelector(state => state.registry)
  const [loading, setLoading] = useState(false)
  const [dialogType, setDialogType] = useState("")
  const [data, setData] = useState([])
  const [total, setTotal] = useState(0)
  const [rowsPerPage, setRowsPerPage] = useState(5)
  const [page, setPage] = useState(0)
  const [currentCheckpoint, setCurrentCheckpoint] = useState(null)
  const [error, setError] = useState('')
  const [isActionRunning, setActionRunning] = useState(false);
  const [scanResults, setScanResults] = useState(null)

  const [checkpointData, setPushCheckpointData] = useState("")
  const [registry, setRegistry] = useState("")

  const [regName, setRegName] = useState("")
  const [regUsername, setRegistryUsername] = useState("")
  const [regPassword, setRegistryPassword] = useState("")

  const [isLogsOpen, setLogsOpen] = useState(false);
  const [logs, setLogs] = useState(null);
  const [searchTerm, setSearchTerm] = useState("")
  const [selectedPod, setSelectedPod] = useState("all")
  const [analysisFilter, setAnalysisFilter] = useState("all")
  const [scanFilter, setScanFilter] = useState("all")

  // useEffect(() => {
  //   console.log({ registryAuthenticated, registryUsername })
  //   if (registryAuthenticated && registryUsername && currentCheckpoint) {
  //     handlePushCheckpoint(currentCheckpoint?.pod_name, currentCheckpoint?.checkpoint_name)
  //   }
  // }, [registryAuthenticated, registryUsername])

  useEffect(() => {
    handleGetCheckpoints();
    handleGetRegistryList();
  }, [])

  const handleGetRegistryList = () => {
    dispatch(registryActions.getList())
  }

  const handlePushCheckpoint = (pod_name, checkpoint_name) => {
    setDialogType("createAndPushCheckpoint")
    setCurrentCheckpoint({
      "pod_name": pod_name,
      "checkpoint_name": checkpoint_name,
      "checkpoint_config_name": registry
    })
  }

  const handleConfirmPushCheckpoint = async () => {
    const { pod_name, checkpoint_name, username } = currentCheckpoint || {}
    if (!registry) return enqueueSnackbar("Please select registry", { variant: "error" })
    setActionRunning(true)
    handleClearDialog()
    enqueueSnackbar(`Creating and pushing checkpoint: ${checkpoint_name} started`, { variant: "info" })

    try {
      const registryData = registryList.find(item => item.name === registry)
      const result = await checkpointApi.pushCheckpoint({
        ...currentCheckpoint,
        username: registryData?.registry_config_details?.username,
        checkpoint_config_name: registryData?.name
      })

      if (!result.message) {
        enqueueSnackbar(`Creating and pushing checkpoint: ${checkpoint_name} failed`, { variant: "error" })
      } else {
        enqueueSnackbar(`Creating and pushing checkpoint: ${checkpoint_name} successful`, { variant: "success" });
      }
      setActionRunning(false)

    } catch (error) {
      console.error("Creating and pushing checkpoint failed, error", error)
      enqueueSnackbar(`Creating and pushing checkpoint: ${checkpoint_name} failed`, { variant: "error" });
      setActionRunning(false)

    }
    handleClearDialog()
  }

  const handleScanCheckpoint = async (pod_name, checkpoint_name) => {
    setDialogType("scanCheckpoint")
    setCurrentCheckpoint({
      pod_name,
      checkpoint_name
    })
    const result = await checkpointApi.scanCheckpoint({
      pod_name,
      checkpoint_name
    })
    console.log("result", result)
  }

  const handleShowScanResults = async (pod_name, checkpoint_name) => {
    setCurrentCheckpoint({
      pod_name,
      checkpoint_name
    })
    const result = await checkpointApi.getScanResults({
      pod_name,
      checkpoint_name
    })
    console.log("result", result)
    setDialogType("scanResults")
    setScanResults(result)

  }

  const handleRowsPerPageChange = (event) => {
    setRowsPerPage(+event.target.value);
    setPage(0);
  };

  const handlePageChange = (event, newPage) => {
    setPage(newPage);
  };

  const handleGetCheckpoints = async () => {
    try {
      setLoading(true)
      // const result = JSON.parse(podsData.pods)
      const result = await checkpointApi.getList()
      setData(result?.checkpoints)
      setTotal(result?.checkpoints.length)
    } catch (error) {
      console.error("Checkpoint list error", error.toString())
    }
    setLoading(false)

  }


  const renderError = () => {
    return (
      <Grid size={4}>
        <Typography color="error">{error}</Typography>
      </Grid>
    )
  }

  //run analysis
  const startCheckpointctl = async (pod_name = "sample_pod", checkpoint_name = "sample_checkpoint") => {
    enqueueSnackbar(`Running analysis for: ${checkpoint_name}`, { variant: "info" });
    try {
      setActionRunning(true);
      setCurrentCheckpoint({ pod_name, checkpoint_name });

      const checkpoint_name_no_ext = checkpoint_name.replace(".tar", "");

      const result = await checkpointApi.runCheckpointctl(pod_name, checkpoint_name_no_ext);
      await handleGetCheckpoints();
      await openLogs(pod_name, checkpoint_name_no_ext);
      enqueueSnackbar(`Finished analysis for: ${checkpoint_name}`, { variant: "success" });
    }
    catch (error) {
      console.error("Failed running analaysis:", error);
      enqueueSnackbar(`Failed running analaysis`, { variant: "error" });

    }
    setActionRunning(false);
    setCurrentCheckpoint(null);

  }

  const handleCreateRegistry = async () => {
    await registryApi.create({
      name: regName,
      registry: registry,
      username: regUsername,
      password: regPassword
    })
    setRegistry(regName)
    handleGetRegistryList()
    handleClearDialog()
    enqueueSnackbar(`Registry: ${regName} successfully added`, { variant: "success" })
  }

  //diaglog for analysis logs

  const openLogs = async (pod_name = "sample_pod", checkpoint_name = "sample_checkpoint") => {
    try {
      setActionRunning(true)
      const checkpoint_name_no_ext = checkpoint_name.replace(".tar", "");

      const result = await checkpointApi.getCheckpointctlLogs(pod_name, checkpoint_name_no_ext);
      setDialogType("log")
      setLogsOpen(true);
      setLogs(result.logs);
      setActionRunning(false)
    } catch (error) {
      setActionRunning(false)
      console.error(error)
      enqueueSnackbar("Failed to load checkpoint logs", { variant: "error" })
    }


  }

  const handleDownloadCheckpoint = async (pod_name, checkpoint_name) => {
    try {
      setActionRunning(true)
      setCurrentCheckpoint({ pod_name, checkpoint_name })
      await checkpointApi.downloadCheckpoint(pod_name, checkpoint_name)
      enqueueSnackbar(`Downloading checkpoint: ${checkpoint_name}`, { variant: "success" })
    } catch (error) {
      console.error("Failed to download checkpoint:", error)
      enqueueSnackbar(`Failed to download checkpoint: ${checkpoint_name}`, { variant: "error" })
    }
    setActionRunning(false)
    setCurrentCheckpoint(null)
  }
  const closeLogs = () => {
    setLogsOpen(false);
    setLogs(null);
  }

  const handleClearDialog = () => {
    setDialogType("")
    setRegName("")
    setRegistryUsername("")
    setRegistryPassword("")
  }

  const renderRegistryLoginForm = () => {
    return (
      <DialogComponent open={!!dialogType} onClose={handleClearDialog} paperProps={{ maxWidth: 500 }}>
        <Box gap={2} display={"flex"} flexDirection={"column"}>
          <Typography variant="h5">Add New Registry</Typography>
          <TextField
            label="Config Name"
            onChange={(e) => setRegName(e.target.value)}
            value={regName}
          />
          <TextField
            label="Registry"
            onChange={(e) => setRegistry(e.target.value)}
            value={registry}
          />
          <TextField
            label="Username"
            onChange={(e) => setRegistryUsername(e.target.value)}
            value={regUsername}
          />
          <TextField
            type='password'
            label="Registry Password"
            onChange={(e) => setRegistryPassword(e.target.value)}
            value={regPassword}
          />
          <Button variant="contained" onClick={handleCreateRegistry}>Add</Button>
        </Box>
      </DialogComponent>
    )
  }

  const renderCreateAnPushCheckpointDialog = () => {
    if (!currentCheckpoint) return
    return (
      <DialogComponent open onClose={() => handleClearDialog()} paperProps={{ maxWidth: 500 }}>
        <Box display={"flex"} flexDirection={"column"} gap={1}>
          <Typography variant='h5' mb={2}>Create and Push Checkpoint Container</Typography>
          <Box display={"flex"}>
            <FormControl sx={{ minWidth: 120 }} size="small" fullWidth variant='outlined'>
              <Select
                value={registry || "default"}
                onChange={(e) => setRegistry(e.target.value)}
              >
                <MenuItem value={"default"} style={{ fontStyle: "italic" }}>Select Registry</MenuItem>
                {registryList.map(item => <MenuItem value={item.name} key={item.name}>{item.name}</MenuItem>)}
              </Select>
            </FormControl>
            <IconButton onClick={() => setDialogType("registryForm")}><AddCircleIcon color="info" /></IconButton>
          </Box>
          <Box p={1} display={"flex"} flexDirection={"column"}>
            <Typography fontWeight={"bold"} display={"inline"}>{`Pod: `}<Typography display={"inline"}>{currentCheckpoint?.pod_name}</Typography></Typography>
            <Typography fontWeight={"bold"} display={"inline"}>{`Checkpoint: `}<Typography display={"inline"} style={{ wordWrap: "break-word" }}>{currentCheckpoint?.checkpoint_name}</Typography></Typography>
          </Box>

          <Button variant="contained" onClick={handleConfirmPushCheckpoint}>Execute</Button>
        </Box>
      </DialogComponent>

    )
  }

  const renderScanResults = () => {
    return (
      <DialogComponent open={!!dialogType} onClose={() => handleClearDialog()} paperProps={{ maxWidth: 800 }}>
        <Typography variant="h5">Scan Results</Typography>
        <Box sx={{ maxHeight: '400px', overflowY: 'auto', whiteSpace: 'pre-wrap', fontFamily: 'monospace', p: 2, bgcolor: '#f5f5f5' }}>
          {scanResults}
        </Box>
      </DialogComponent>
    )
  }
  const renderDialog = () => {
    const dialogContent = {
      log: (
        <BeautifulAnalysisResults 
          data={logs} 
          open={isLogsOpen} 
          onClose={closeLogs} 
          title="Analysis Results" 
        />
      ),
      registryForm: renderRegistryLoginForm(),
      createAndPushCheckpoint: renderCreateAnPushCheckpointDialog(),
      scanResults: renderScanResults()
    }
    return dialogContent[dialogType]
  }

  const tableHeaders = [
    { name: "Checkpoint", key: "checkpoint_name" },
    { name: "Pod Name", key: "pod_name" },
    {
      name: "Actions", key: "", action: ({ pod_name, checkpoint_name, analysis_result, scan_result }) => (
        <>
          {
            isActionRunning && (currentCheckpoint?.checkpoint_name === checkpoint_name) ? <CircularProgress size={24} /> :
              <Stack direction="row" spacing={1}>
                <Tooltip title={analysis_result ? "Re-analyze" : "Analyze"}>
                  <IconButton aria-label="analyze" onClick={() => startCheckpointctl(pod_name, checkpoint_name)}>
                    <PlayArrowRoundedIcon />
                  </IconButton>
                </Tooltip>
                {
                  analysis_result &&
                  <Tooltip title="Show Analysis">
                    <IconButton aria-label="show analysis" onClick={() => openLogs(pod_name, checkpoint_name)}>
                      <TextSnippetRoundedIcon />
                    </IconButton>
                  </Tooltip>
                }
                {/* <IconButton onClick={() => handleScanCheckpoint(pod_name, checkpoint_name)}>
                  <Tooltip title="Scan">
                    <ScanIcon />
                  </Tooltip>
                </IconButton>
                {scan_result && <IconButton onClick={() => handleShowScanResults(pod_name, checkpoint_name)}>
                  <Tooltip title="Scan Results">
                    <ScanResultsIcon />
                  </Tooltip>
                </IconButton>} */}

                <IconButton onClick={() => handlePushCheckpoint(pod_name, checkpoint_name)}>
                  <Tooltip title="Upload Checkpoint">
                    <FileUploadIcon />
                  </Tooltip>
                </IconButton>
                <IconButton onClick={() => handleDownloadCheckpoint(pod_name, checkpoint_name)}>
                  <Tooltip title="Download Checkpoint">
                    <DownloadIcon />
                  </Tooltip>
                </IconButton>
              </Stack>
          }
        </>
      )
    },
  ]

  const filteredData = data.filter(item => {
    const searchFields = [
      item.pod_name,
      item.checkpoint_name
    ];
    const matchesSearch = searchFields.some(field => String(field).toLowerCase().includes(searchTerm.toLowerCase()))
    const matchesPod = selectedPod === "all" || item.pod_name === selectedPod
    const matchesAnalysis = analysisFilter === "all" ? true : analysisFilter === "analyzed" ? !!item.analysis_result : !item.analysis_result
    const matchesScan = scanFilter === "all" ? true : scanFilter === "scanned" ? !!item.scan_result : !item.scan_result

    return matchesSearch && matchesPod && matchesAnalysis && matchesScan
  })

  const podOptions = useMemo(() => {
    return Array.from(new Set(data.map(item => item.pod_name).filter(Boolean)))
  }, [data])

  const clearFilters = () => {
    setSearchTerm("")
    setSelectedPod("all")
    setAnalysisFilter("all")
    setScanFilter("all")
    setPage(0)
  }

  useEffect(() => {
    setPage(0)
  }, [searchTerm, selectedPod, analysisFilter, scanFilter])


  return (
    <CustomerContainer title="Checkpoints" subtitle="Checkpoint List">
      {loading ? <Loading /> : (
        <>
          <Paper elevation={0} sx={{ px: 3, py: 1, bgcolor: 'background.paper', borderRadius: 2 }}>
            {renderError()}
            {renderDialog()}
            <Box sx={{ mt: 2, mb: 2 }}>
              <Typography variant="h6" gutterBottom sx={{ mb: 2 }}>
                Search & Filters
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 2 }}>
                <TextField
                  sx={{ width: '300px', minWidth: '200px' }}
                  size="small"
                  placeholder="Search by pod name or checkpoint name"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
                <FormControl sx={{ minWidth: 180 }} size="small">
                  <Select
                    value={selectedPod}
                    onChange={(e) => setSelectedPod(e.target.value)}
                    displayEmpty
                  >
                    <MenuItem value="all">All Pods</MenuItem>
                    {podOptions.map(pod => (
                      <MenuItem key={pod} value={pod}>{pod}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <FormControl sx={{ minWidth: 150 }} size="small">
                  <Select
                    value={analysisFilter}
                    onChange={(e) => setAnalysisFilter(e.target.value)}
                    displayEmpty
                  >
                    <MenuItem value="all">All Analysis</MenuItem>
                    <MenuItem value="analyzed">Analyzed</MenuItem>
                    <MenuItem value="not-analyzed">Not Analyzed</MenuItem>
                  </Select>
                </FormControl>
                <FormControl sx={{ minWidth: 150 }} size="small">
                  <Select
                    value={scanFilter}
                    onChange={(e) => setScanFilter(e.target.value)}
                    displayEmpty
                  >
                    <MenuItem value="all">All Scan Status</MenuItem>
                    <MenuItem value="scanned">Scanned</MenuItem>
                    <MenuItem value="not-scanned">Not Scanned</MenuItem>
                  </Select>
                </FormControl>
                <Button
                  variant="outlined"
                  startIcon={<ClearIcon />}
                  onClick={clearFilters}
                  size="small"
                  disabled={searchTerm === "" && selectedPod === "all" && analysisFilter === "all" && scanFilter === "all"}
                >
                  Clear Filters
                </Button>
              </Box>
              {filteredData.length !== data.length && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  Showing {filteredData.length} of {data.length} checkpoints
                </Typography>
              )}
            </Box>
            <TableComponent
              classes={classes}
              data={filteredData}
              tableHeaders={tableHeaders}
              total={filteredData.length}
              rowsPerPage={rowsPerPage}
              page={page}
              handleRowsPerPageChange={handleRowsPerPageChange}
              handlePageChange={handlePageChange}
            />
          </Paper>
        </>
      )}
    </CustomerContainer>
  )
}

export default CheckpointsScreen;