import { Box, Button, CircularProgress, Grid2 as Grid, TextField, Typography, Card, Paper, FormLabel, Chip } from "@mui/material"
import { useEffect, useState } from "react";
import TableComponent from "../common/Table";
import { useSnackbar } from 'notistack';
import Stack from '@mui/material/Stack';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import { useDispatch, useSelector } from "react-redux";
import DialogComponent from "../common/Dialog";
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import { Loading } from "../common/loading";
import AddIcon from '@mui/icons-material/Add';
import { CustomerContainer } from "../common/CustomContainer";
import { validateFormData } from "../../utils/validateFormData";
import { Visibility as WatchersIcon, PlayArrow as StartIcon, Stop as StopIcon, Info as InfoIcon } from '@mui/icons-material';
import { snapWatcherApi } from '../../api/snapWatcherApi';
import SnapWatcherStatus from './SnapWatcherStatus';

const SnapWatcherScreen = ({ classes }) => {
  const dispatch = useDispatch()
  const { enqueueSnackbar } = useSnackbar();
  const { selectedCluster = "" } = useSelector(state => state.cluster)
  const [loading, setLoading] = useState(false)
  const [dialogType, setDialogType] = useState("")
  const [data, setData] = useState([])
  const [total, setTotal] = useState(0)
  const [rowsPerPage, setRowsPerPage] = useState(5)
  const [page, setPage] = useState(0)
  const [error, setError] = useState('')
  const [currentRowItem, setCurrentRowItem] = useState(null)
  const [isEdit, setIsEdit] = useState(false)
  const [watcherName, setWatcherName] = useState("")
  const [watcherScope, setWatcherScope] = useState("cluster")
  const [watcherTrigger, setWatcherTrigger] = useState("startupProbe")
  const [watcherNamespace, setWatcherNamespace] = useState("")
  const [isActionLoading, setIsActionLoading] = useState(false)
  const [searchTerm, setSearchTerm] = useState("")
  const [errors, setErrors] = useState({})
  const [watchers, setWatchers] = useState([])
  const [statusView, setStatusView] = useState(false)
  const [selectedWatcherForStatus, setSelectedWatcherForStatus] = useState(null)

  useEffect(() => {
    handleGetWatcherList();
  }, [selectedCluster])

  const handleGetWatcherList = async () => {
    if (!selectedCluster) {
      setWatchers([])
      return
    }
    
    setLoading(true)
    try {
      const response = await snapWatcherApi.getSnapWatchers(selectedCluster.name)
      console.log("API response:", response)
      if (response.success) {
        console.log("Watchers from API:", response.watchers)
        setWatchers(response.watchers || [])
      } else {
        setWatchers([])
      }
    } catch (error) {
      console.error("Error fetching watchers:", error)
      setWatchers([])
    } finally {
      setLoading(false)
    }
  }

  const handleRowsPerPageChange = (event) => {
    setRowsPerPage(+event.target.value);
    setPage(0);
  };

  const handlePageChange = (event, newPage) => {
    setPage(newPage);
  };

  const handleDeleteWatcher = async () => {
    try {
      setIsActionLoading(true)
      await snapWatcherApi.deleteSnapWatcher(currentRowItem.name)
      handleGetWatcherList()
      enqueueSnackbar(`Watcher: ${currentRowItem.name} successfully deleted`, { variant: "success" })
    } catch (error) {
      console.error("Watcher delete error", error.toString())
      enqueueSnackbar(`Watcher: ${currentRowItem.name} deletion failed`, { variant: "error" })
    }
    handleClearDialog()
  }

  const handleStartWatcher = async (watcher) => {
    console.log("Starting watcher:", watcher)
    console.log("Watcher name:", watcher.name)
    try {
      setIsActionLoading(true)
      await snapWatcherApi.startSnapWatcher(watcher.name)
      setWatchers(prev => 
        prev.map(w => 
          w.name === watcher.name 
            ? { ...w, status: 'running' }
            : w
        )
      )
      enqueueSnackbar(`Watcher: ${watcher.name} started successfully`, { variant: "success" })
    } catch (error) {
      console.error("Watcher start error", error.toString())
      enqueueSnackbar(`Watcher: ${watcher.name} start failed`, { variant: "error" })
    } finally {
      setIsActionLoading(false)
    }
  }

  const handleStopWatcher = async (watcher) => {
    try {
      setIsActionLoading(true)
      await snapWatcherApi.stopSnapWatcher(watcher.name)
      setWatchers(prev => 
        prev.map(w => 
          w.name === watcher.name 
            ? { ...w, status: 'stopped' }
            : w
        )
      )
      enqueueSnackbar(`Watcher: ${watcher.name} stopped successfully`, { variant: "success" })
    } catch (error) {
      console.error("Watcher stop error", error.toString())
      enqueueSnackbar(`Watcher: ${watcher.name} stop failed`, { variant: "error" })
    } finally {
      setIsActionLoading(false)
    }
  }

  const handleSubmit = async () => {
    if (!selectedCluster) {
      enqueueSnackbar("No cluster selected", { variant: "error" })
      return;
    }
    
    const requestBody = {
      name: watcherName,
      cluster_name: selectedCluster.name,
      cluster_config: {
        cluster_config_details: selectedCluster.cluster_config_details,
        name: selectedCluster.name
      },
      scope: watcherScope,
      trigger: watcherTrigger,
      namespace: watcherNamespace
    }
    
    // Custom validation for watcher form
    const validationErrors = {}
    if (!watcherName || watcherName.trim() === "") {
      validationErrors.name = "Watcher Name is required"
    }
    if (!watcherScope || watcherScope.trim() === "") {
      validationErrors.scope = "Scope is required"
    }
    if (!watcherTrigger || watcherTrigger.trim() === "") {
      validationErrors.trigger = "Trigger is required"
    }
    if (watcherScope === 'namespace' && (!watcherNamespace || watcherNamespace.trim() === "")) {
      validationErrors.namespace = "Namespace is required for namespace scope"
    }
    
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors)
      return;
    }
    
    // Clear any existing errors
    setErrors({})

    if (isEdit) {
      setIsActionLoading(true)
      enqueueSnackbar(`Watcher: ${watcherName} update initiated`, { variant: "info" })
      try {
        await snapWatcherApi.updateSnapWatcher(currentRowItem.name, requestBody)
        enqueueSnackbar(`Watcher: ${watcherName} successfully updated`, { variant: "success" })
      } catch (error) {
        console.error("Watcher update error", error.toString())
        enqueueSnackbar(`Watcher: ${watcherName} update failed`, { variant: "error" })
      }
    } else {
      enqueueSnackbar(`Watcher: ${watcherName} creation and startup initiated`, { variant: "info" })
      try {
        await snapWatcherApi.createSnapWatcher(requestBody)
        enqueueSnackbar(`Watcher: ${watcherName} successfully created and started`, { variant: "success" })
      } catch (error) {
        console.error("Watcher creation error", error)
        enqueueSnackbar(`Watcher: ${watcherName} creation failed: ${error.response?.data?.detail || error.message}`, { variant: "error" })
      }
    }
    handleGetWatcherList()
    handleClearDialog()
  }

  const handleOpenEditDialog = (watcher) => {
    setDialogType("watcherForm")
    setCurrentRowItem(watcher)
    setWatcherName(watcher.name)
    setWatcherScope(watcher.scope)
    setWatcherTrigger(watcher.trigger)
    setWatcherNamespace(watcher.namespace || "")
    setIsEdit(true)
  }

  const handleOpenDeleteDialog = (watcher) => {
    setDialogType("watcherDelete")
    setCurrentRowItem(watcher)
  }

  const handleClearDialog = () => {
    setIsActionLoading(false)
    setLoading(false)
    setDialogType("")
    setWatcherName("")
    setWatcherScope("cluster")
    setWatcherTrigger("startupProbe")
    setWatcherNamespace("")
    setErrors({})
    setIsEdit(false)
    setCurrentRowItem(null)
    setPage(0)
  }

  const handleViewStatus = (watcher) => {
    setSelectedWatcherForStatus(watcher)
    setStatusView(true)
  }

  const handleCloseStatusView = () => {
    setStatusView(false)
    setSelectedWatcherForStatus(null)
  }

  const renderWatcherDeleteDialog = () => {
    return (
      <DialogComponent open={!!dialogType} onClose={() => handleClearDialog("")} paperProps={{ maxWidth: 500 }}>
        <Box gap={2} display={"flex"} flexDirection={"column"}>
          <Typography variant="h5">Delete Watcher</Typography>
          <Typography>Are you sure you want to delete this watcher?</Typography>
          <Button variant="contained" onClick={() => handleDeleteWatcher()}>Delete</Button>
        </Box>
      </DialogComponent>
    )
  }

  const renderWatcherForm = () => {
    return (
      <DialogComponent open={!!dialogType} onClose={() => handleClearDialog("")} paperProps={{ maxWidth: 500 }}>
        <Box gap={2} display={"flex"} flexDirection={"column"}>
          <Typography variant="h5">Add New Watcher</Typography>
          <TextField
            label="Watcher Name"
            onChange={(e) => setWatcherName(e.target.value)}
            value={watcherName}
            disabled={isEdit}
            helperText={!!errors?.name && "Watcher Name is required"}
            error={!!errors?.name}
          />
          <TextField
            label="Scope"
            select
            onChange={(e) => setWatcherScope(e.target.value)}
            value={watcherScope}
            helperText={!!errors?.scope && "Scope is required"}
            error={!!errors?.scope}
            SelectProps={{
              native: true,
            }}
          >
            <option value="cluster">Cluster</option>
            <option value="namespace">Namespace</option>
          </TextField>
          {watcherScope === 'namespace' && (
            <TextField
              label="Namespace"
              onChange={(e) => setWatcherNamespace(e.target.value)}
              value={watcherNamespace}
              helperText="Namespace to monitor"
            />
          )}
          <TextField
            label="Trigger"
            select
            onChange={(e) => setWatcherTrigger(e.target.value)}
            value={watcherTrigger}
            helperText={!!errors?.trigger && "Trigger is required"}
            error={!!errors?.trigger}
            SelectProps={{
              native: true,
            }}
          >
            <option value="startupProbe">Startup Probe</option>
          </TextField>
          <Button variant="contained" onClick={handleSubmit}>Add</Button>
        </Box>
      </DialogComponent>
    )
  }

  const renderDialog = () => {
    const dialogContent = {
      watcherForm: renderWatcherForm(),
      watcherDelete: renderWatcherDeleteDialog(),
    }
    return dialogContent[dialogType]
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'running': return 'success';
      case 'stopped': return 'default';
      case 'error': return 'error';
      default: return 'default';
    }
  }

  const tableHeaders = [
    { name: "Name", key: "name" },
    { name: "Scope", key: "scope" },
    { name: "Trigger", key: "trigger" },
    { name: "Namespace", key: "namespace" },
    { name: "Status", key: "status", render: (data) => {
      return (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box
            sx={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: data.status === 'running' ? 'success.main' : 'grey.400'
            }}
          />
          <Chip 
            label={data.status} 
            color={data.status === 'running' ? 'success' : 'default'}
            size="small"
            variant="outlined"
          />
        </Box>
      );
    }},
    {
      name: "Actions", key: "", action: (data) => {
        console.log("Table action data:", data)
        return (
          <>
            {
              <Stack direction="row" spacing={1}>
                {currentRowItem && currentRowItem?.name === data?.name && isActionLoading ? <CircularProgress />
                  :
                  <>
                    <Tooltip title={data.status === 'running' ? "Stop Watcher" : "Start Watcher"}>
                      <IconButton 
                        aria-label={data.status === 'running' ? "stop watcher" : "start watcher"} 
                        onClick={() => {
                          console.log("Button clicked, data:", data)
                          data.status === 'running' ? handleStopWatcher(data) : handleStartWatcher(data)
                        }} 
                        size="small"
                        color={data.status === 'running' ? "warning" : "success"}
                      >
                        {data.status === 'running' ? <StopIcon fontSize="small" /> : <StartIcon fontSize="small" />}
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="View Status">
                      <IconButton aria-label="view status" onClick={() => handleViewStatus(data)} size="small">
                        <InfoIcon fontSize="small" color="info" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete Watcher">
                      <IconButton aria-label="delete watcher" onClick={() => handleOpenDeleteDialog(data)} size="small">
                        <DeleteIcon fontSize="small" color="error" />
                      </IconButton>
                    </Tooltip>
                  </>
                }
              </Stack>
            }
          </>
        )
      }
    },
  ]

  const renderError = () => {
    return (
      <Grid size={4}>
        <Typography color="error">{error}</Typography>
      </Grid>
    )
  }

  const filteredData = watchers.filter(item => {
    const searchFields = [
      item.name,
      item.scope,
      item.trigger,
      item.namespace
    ];
    return searchFields.some(field => String(field).toLowerCase().includes(searchTerm.toLowerCase()))
  })

  if (!selectedCluster) {
    return (
      <CustomerContainer title="SnapWatcher" subtitle="Manage cluster watchers">
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '50vh',
            textAlign: 'center',
          }}
        >
          <WatchersIcon sx={{ fontSize: 60, color: 'primary.main', mb: 2 }} />
          <Typography variant="h5" color="primary" sx={{ mb: 2 }}>
            No Cluster Selected
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Select a cluster to manage SnapWatchers
          </Typography>
        </Box>
      </CustomerContainer>
    );
  }

  return (
    <CustomerContainer title="SnapWatcher" subtitle={`Manage watchers for ${selectedCluster.name}`}>
      {loading ? <Loading /> : (
        <>
          {statusView ? (
            <Box sx={{ mb: 3 }}>
              <Button
                variant="outlined"
                onClick={handleCloseStatusView}
                sx={{ mb: 2 }}
              >
                ← Back to Watchers
              </Button>
              {selectedWatcherForStatus && (
                <SnapWatcherStatus watcherName={selectedWatcherForStatus.name} />
              )}
            </Box>
          ) : (
            <>
              <Button
                variant="contained"
                onClick={() => setDialogType("watcherForm")}
                sx={{
                  backgroundColor: 'primary.main',
                  borderRadius: '8px',
                  textTransform: 'none',
                  mb: 2,
                  px: 3,
                  py: 1,
                  '&:hover': {
                    backgroundColor: 'primary.dark',
                    boxShadow: 2,
                  },
                }}
                startIcon={<AddIcon />}
              >
                Add SnapWatcher
              </Button>
              <Paper elevation={0} sx={{ px: 3, py: 1, bgcolor: 'background.paper', borderRadius: 2 }}>
                {renderError()}
                {renderDialog()}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, marginBlock: 2, ml: 1 }}>
                  <Typography variant="h6" gutterBottom component="div">
                    Search
                  </Typography>
                  <TextField
                    sx={{ width: '300px' }}
                    size="small"
                    placeholder="Name, Scope, Trigger, Namespace"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
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
        </>
      )}
    </CustomerContainer>
  )
}

export default SnapWatcherScreen;
