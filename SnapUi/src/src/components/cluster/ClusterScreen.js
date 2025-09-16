import { Box, Typography, Button, Select, MenuItem, FormControl, TextField, Stack, Grid2 as Grid, Card, CardContent, CircularProgress, Paper, Divider, Chip, IconButton, Tooltip, FormControlLabel, InputLabel, Tabs, Tab } from "@mui/material"
import { useDispatch, useSelector } from "react-redux";
import { Loading } from "../common/loading";
import { clusterActions } from "../../features/cluster/clusterSlice";
import { useEffect, useState } from "react";
import DialogComponent from "../common/Dialog";
import { useSnackbar } from "notistack";
import { clusterApi } from "../../api/clusterApi";
import { clusterCacheApi } from "../../api/clusterCacheApi";
import { useNavigate } from "react-router-dom";
import { Delete, SystemUpdateAlt as InstallIcon, SafetyCheck as VerifyIcon, Add as AddIcon, Cloud as CloudIcon, Storage as StorageIcon, Security as SecurityIcon, CloudUpload, Edit } from "@mui/icons-material";
import { removeCookie } from "../../utils/cookies";
import PolylineIcon from '@mui/icons-material/Polyline';
import LibraryBooksIcon from '@mui/icons-material/LibraryBooks';
import { CustomerContainer } from "../common/CustomContainer";
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import WarningIcon from '@mui/icons-material/Warning';
import { YamlEditor } from "../common/YamlViewer";
import Editor from "@monaco-editor/react";

const ClusterScreen = () => {
  const { enqueueSnackbar } = useSnackbar();
  const navigate = useNavigate()

  const dispatch = useDispatch()
  const {
    kubeAuthenticated = false,
    error: clusterError = "",
    checkpointingEnabled = false,
    selectedCluster = "",
    loading = {}
  } = useSelector(state => state.cluster)

  const { loading: authLoading = false } = useSelector(state => state.auth)

  const [clusterType, setClusterType] = useState("openshift")
  const [clusterEditing, setClusterEditing] = useState(false)
  const [dialogType, setDialogType] = useState("")
  const [dialogData, setDialogData] = useState(null)
  const [clusterName, setClusterName] = useState("");
  const [clusterUrl, setClusterUrl] = useState("");
  const [clusterToken, setClusterToken] = useState("");
  const [sshKey, setSshkey] = useState(null);
  const [clusterFormErrors, setClusterFormErrors] = useState({});
  const [statLoading, setStatLoading] = useState(false)
  const [stats, setStats] = useState({ total_pods: 0, total_checkpoints: 0 });
  const [playbookConfigs, setPlaybookConfigs] = useState([])
  const [availableRegistries, setAvailableRegistries] = useState([])
  
  // Cluster cache management state
  const [clusterCacheDialogOpen, setClusterCacheDialogOpen] = useState(false)
  const [clusterCache, setClusterCache] = useState(null)
  const [clusterCacheLoading, setClusterCacheLoading] = useState(false)
  const [selectedCacheRegistry, setSelectedCacheRegistry] = useState("")
  const [cacheRepo, setCacheRepo] = useState("snap_images")

  useEffect(() => {
    const fetchStats = async () => {
      if (!kubeAuthenticated) return setStats({ total_pods: 0, total_checkpoints: 0 })
      setStatLoading(true)
      try {
        const data = await clusterApi.getStatistics();
        setStats(data);
      } catch (error) {
        enqueueSnackbar("Failed to get statistics", { variant: "error" })
      }

      setStatLoading(false)
    };

    fetchStats();
  }, [kubeAuthenticated]);

  // Fetch available registries when component mounts
  useEffect(() => {
    const fetchRegistries = async () => {
      try {
        const response = await fetch(`${window.ENV.apiUrl}/config/registry/list`);
        const data = await response.json();
        if (data.success) {
          setAvailableRegistries(data.registry_configs || []);
        }
      } catch (error) {
        console.error("Failed to fetch registries:", error);
      }
    };

    fetchRegistries();
  }, []);

  const handleSubmitCluster = async () => {
    // Clear previous errors
    setClusterFormErrors({})
    
    // Validation
    const errors = {}
    if (!clusterName.trim()) errors.name = "Cluster name is required"
    if (!clusterUrl.trim()) errors.url = "Cluster API URL is required"
    if (!clusterToken.trim()) errors.token = "Token is required"
    
    if (Object.keys(errors).length > 0) {
      setClusterFormErrors(errors)
      return
    }

    const clusterData = {
      name: clusterName,
      kube_api_url: clusterUrl,
      token: clusterToken
    }
    
    try {
      if (clusterEditing) {
        enqueueSnackbar("Update cluster initiated...", { variant: "info" })
        await clusterApi.update(clusterData)
      } else {
        enqueueSnackbar("Creating cluster initiated...", { variant: "info" })
        await clusterApi.create(clusterData)
      }

      if (sshKey) {
        const formData = new FormData()
        formData.append("file", sshKey)
        await clusterApi.uploadSshkey(clusterName, formData)
        dispatch(clusterActions.getList())
      }
      handleClearDialog()
      enqueueSnackbar(`Cluster ${clusterEditing ? "updated" : "added"} successfully`, { variant: "success" })
    } catch (error) {
      console.error("Cluster operation error:", error)
      enqueueSnackbar(`Failed to ${clusterEditing ? "update" : "create"} cluster`, { variant: "error" })
    }
  }

  const handleShowClusterConfig = () => {
    const { name, cluster_config_details } = selectedCluster || {}
    const { kube_api_url, token } = cluster_config_details || {}
    setClusterEditing(true)
    setClusterName(name)
    setClusterUrl(kube_api_url)
    setClusterToken(token || "")
    setDialogType("clusterForm")
  }

  const handleDeleteCluster = async () => {
    try {
      await clusterApi.remove(selectedCluster.name)
      removeCookie("selectedCluster")
      dispatch(clusterActions.clearState())
      dispatch(clusterActions.getList())
      enqueueSnackbar(`Cluster: ${selectedCluster.name} successfully deleted`, { variant: "success" })
    } catch (error) {
      console.error("Cluster delete error", error.toString())
      enqueueSnackbar(`Cluster: ${selectedCluster.name} deletion failed`, { variant: "error" })
    }
    setDialogType("")
  }

  const handleClusterVerification = async () => {
    enqueueSnackbar("Cluster verification started", { variant: "info" })
    const { payload = null } = await dispatch(clusterActions.verify(selectedCluster.name))
    const { success = false } = payload || {}
    if (!success) {
      enqueueSnackbar("Cluster verification failed", { variant: "error" })
      return
    }
    enqueueSnackbar("Cluster verification successful", { variant: "success" })
  }

  const handleEnableCheckpointing = async (clusterType) => {
    enqueueSnackbar("Enable checkpointing started", { variant: "info" })
    setDialogType("")
    const { payload = null } = await dispatch(clusterActions.enableCheckpointing({ clusterType, clusterName: selectedCluster.name }))
    const { success = false } = payload || {}
    if (!success) {
      enqueueSnackbar("Enable checkpointing failed", { variant: "error" })
    } else {
      enqueueSnackbar("Enable checkpointing successful", { variant: "success" })
    }
  }

  const handleInstallRunc = async () => {
    try {
      enqueueSnackbar("Installing runc", { variant: "info" })
      const result = await dispatch(clusterActions.installRunC(selectedCluster.name))
      if (!result?.success) {
        enqueueSnackbar(`Failed to install runc`, { variant: "error" })
        return
      }
      enqueueSnackbar("RunC installation successful", { variant: "success" })
    } catch (error) {
      console.error("Failed to install runc", error)
      enqueueSnackbar("Failed to install runc", { variant: "error" })
    }
  }

  const handleShowNodeConfig = async () => {
    const { success = false, message = "", cluster_config = null } = await clusterApi.getNodeConfig(selectedCluster.name)
    if (!success) {
      enqueueSnackbar(`Node configuration failed, ${message}`, { variant: "error" })
    } else {
      setDialogType("nodeConfig")
      setDialogData(cluster_config)
    }
  }

  const handlePlaybookConfigs = async () => {
    setDialogType("playbookConfigs")
    setDialogData({ loading: true })

    const result = await clusterApi.getPlaybookConfigs()
    if (!result?.success) {
      enqueueSnackbar(`Failed to get playbook configs`, { variant: "error" })
      return
    }
    setDialogData(null)
    setPlaybookConfigs(result?.config_list)
  }

  const handleEnableCheckpointingConfirmation = (type) => {
    setDialogType("confirmEnableCheckpoint")
    setDialogData(type)
  }

  const handleUpdateNodeConfig = async () => {
    enqueueSnackbar("Updating node configuration started", { variant: "info" })
    const { success = false, message = "" } = await clusterApi.updateNodeConfig(selectedCluster.name, dialogData)
    if (!success) {
      enqueueSnackbar(`Node configuration update failed, ${message}`, { variant: "error" })
    } else {
      enqueueSnackbar("Node configuration update successful", { variant: "success" })
    }
    setDialogType("")
  }

  const handleUpdatePlaybookConfig = async () => {
    enqueueSnackbar("Updating playbook configuration started", { variant: "info" })
    const { success = false, message = "" } = await clusterApi.updatePlaybookConfig(dialogData)
    if (!success) {
      enqueueSnackbar(`Playbook configuration update failed, ${message}`, { variant: "error" })
    } else {
      enqueueSnackbar("Playbook configuration update successful", { variant: "success" })
    }
    setDialogType("")
  }

  const handleShowYaml = async (yaml) => {
    setDialogType("playbookConfigEditor")
    setDialogData(yaml)
  }

  const handleClearDialog = () => {
    setDialogType("")
    setClusterName("")
    setClusterUrl("")
    setClusterToken("")
    setSshkey(null)
    setClusterFormErrors(null)
    setClusterEditing(false)
  }

  const handleShowClusterCacheConfig = async () => {
    if (!selectedCluster) return;
    
    setClusterCacheDialogOpen(true);
    setClusterCacheLoading(true);
    
    try {
      const response = await clusterCacheApi.get(selectedCluster.name);
      if (response.success && response.cluster_cache_details) {
        setClusterCache(response.cluster_cache_details);
        setSelectedCacheRegistry(response.cluster_cache_details.registry);
        setCacheRepo(response.cluster_cache_details.repo);
      } else {
        setClusterCache(null);
        setSelectedCacheRegistry("");
        setCacheRepo("snap_images");
      }
    } catch (error) {
      console.error("Failed to fetch cluster cache:", error);
      setClusterCache(null);
      setSelectedCacheRegistry("");
      setCacheRepo("snap_images");
    }
    
    setClusterCacheLoading(false);
  }

  const handleUpdateClusterCache = async () => {
    if (!selectedCluster || !selectedCacheRegistry) {
      enqueueSnackbar("Please select a registry", { variant: "error" });
      return;
    }

    setClusterCacheLoading(true);
    try {
      const response = await clusterCacheApi.update({
        cluster: selectedCluster.name,
        registry: selectedCacheRegistry,
        repo: cacheRepo
      });

      if (response.success) {
        enqueueSnackbar("Cluster cache updated successfully", { variant: "success" });
        setClusterCacheDialogOpen(false);
        // Refresh the cache data
        handleShowClusterCacheConfig();
      } else {
        enqueueSnackbar(`Failed to update cluster cache: ${response.message}`, { variant: "error" });
      }
    } catch (error) {
      console.error("Failed to update cluster cache:", error);
      enqueueSnackbar("Failed to update cluster cache", { variant: "error" });
    }
    setClusterCacheLoading(false);
  }

  const handleCreateClusterCache = async () => {
    if (!selectedCluster || !selectedCacheRegistry) {
      enqueueSnackbar("Please select a registry", { variant: "error" });
      return;
    }

    setClusterCacheLoading(true);
    try {
      const response = await clusterCacheApi.create({
        cluster: selectedCluster.name,
        registry: selectedCacheRegistry,
        repo: cacheRepo
      });

      if (response.success) {
        enqueueSnackbar("Cluster cache created successfully", { variant: "success" });
        setClusterCacheDialogOpen(false);
        // Refresh the cache data
        handleShowClusterCacheConfig();
      } else {
        enqueueSnackbar(`Failed to create cluster cache: ${response.message}`, { variant: "error" });
      }
    } catch (error) {
      console.error("Failed to create cluster cache:", error);
      enqueueSnackbar("Failed to create cluster cache", { variant: "error" });
    }
    setClusterCacheLoading(false);
  }

  const renderAuthenticationDetails = () => {
    return (
      <TextField
        label="Token"
        type="password"
        onChange={(e) => setClusterToken(e.target.value)}
        value={clusterToken}
        helperText={clusterFormErrors?.token}
        error={!!clusterFormErrors?.token}
      />
    )
  }

  const renderClusterForm = () => {
    return (
      <DialogComponent
        open
        onClose={handleClearDialog}
        paperProps={{
          maxWidth: 500,
          sx: { borderRadius: 2 }
        }}
      >
        <Box sx={{ p: 1 }}>
          <Typography variant="h5" sx={{ fontWeight: 'bold', mb: 1 }}>
            Cluster Configuration
          </Typography>
        </Box>
        <Box gap={2} display={"flex"} flexDirection={"column"}>
          <TextField
            label="Cluster Name"
            onChange={(e) => setClusterName(e.target.value)}
            value={clusterName}
            disabled={clusterEditing}
            helperText={clusterFormErrors?.name}
            error={!!clusterFormErrors?.name}
          />
          <TextField
            label="Cluster Api Url"
            onChange={(e) => setClusterUrl(e.target.value)}
            value={clusterUrl}
            helperText={clusterFormErrors?.url}
            error={!!clusterFormErrors?.url}
          />

          {renderAuthenticationDetails()}
          <Button variant="outlined" component="label" style={{ width: 200, textTransform: "capitalize" }} startIcon={<CloudUpload />}>
            Upload SSH Key
            <input
              type="file"
              accept="*"
              hidden
              onChange={(e) => setSshkey(e.target.files[0])}
            />
          </Button>
          {sshKey && <Typography variant="body2">{sshKey.name}</Typography>}
          
          <Button variant="contained" style={{ textTransform: "capitalize" }} onClick={handleSubmitCluster}>Submit</Button>
        </Box>
      </DialogComponent>
    )
  }

  const renderSelectClusterType = () => {
    return (
      <DialogComponent
        open
        onClose={handleClearDialog}
        paperProps={{
          maxWidth: 500,
          sx: { borderRadius: 2 }
        }}
      >
        <Box sx={{ p: 1 }}>
          <Typography variant="h5" sx={{ fontWeight: 'bold' }}>
            Select Cluster Type To Enable
          </Typography>
          <Box sx={{ display: 'flex', gap: 5, justifyContent: 'center', mt: 3 }}>
            <Button variant="outlined" onClick={() => handleEnableCheckpointingConfirmation("openshift")} style={{ height: 50 }}>Openshift</Button>
            <Button variant="outlined" onClick={() => handleEnableCheckpointingConfirmation("kubernetes")}>Kubernetes</Button>
          </Box>
        </Box>
      </DialogComponent>
    )
  }

  const renderDeleteClusterDialog = () => {
    return (
      <DialogComponent
        open={!!dialogType}
        onClose={handleClearDialog}
        paperProps={{
          maxWidth: 500,
          sx: { borderRadius: 2 }
        }}
      >
        <Box sx={{ p: 1 }}>
          <Typography variant="h5" sx={{ fontWeight: 'bold', mb: 2 }}>
            Delete Cluster
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
            Are you sure you want to delete the cluster "{selectedCluster.name}"? This action cannot be undone.
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
            <Button
              variant="outlined"
              onClick={() => setDialogType("")}
              sx={{ textTransform: 'none' }}
            >
              Cancel
            </Button>
            <Button
              variant="contained"
              color="error"
              onClick={handleDeleteCluster}
              sx={{ textTransform: 'none' }}
            >
              Delete Cluster
            </Button>
          </Box>
        </Box>
      </DialogComponent>
    )
  }

  const renderConfirmEnableCheckpoint = () => {
    return (
      <DialogComponent
        open={!!dialogType}
        onClose={handleClearDialog}
        paperProps={{
          maxWidth: 500,
          sx: { borderRadius: 2 }
        }}
      >
        <Box sx={{ p: 1 }}>
          <Typography variant="h5" sx={{ fontWeight: 'bold', mb: 2 }}>
            <WarningIcon color="warning" sx={{ verticalAlign: 'middle', mr: 1, mt: -.5 }} />
            Enabling Checkpointing
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
            Warning: Enabling checkpointing will require a restart of the cluster. Are you sure you want to proceed?
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
            <Button
              variant="outlined"
              onClick={() => setDialogType("")}
              sx={{ textTransform: 'none' }}
            >
              Cancel
            </Button>
            <Button
              variant="contained"
              onClick={() => handleEnableCheckpointing(dialogData)}
              sx={{ textTransform: 'none' }}
            >
              Confirm
            </Button>
          </Box>
        </Box>
      </DialogComponent>
    )
  }

  const renderJsonEditorDialog = () => {
    return (
      <DialogComponent
        open={!!dialogType}
        onClose={handleClearDialog}
        paperProps={{
          maxWidth: 800,
          sx: { borderRadius: 2 }
        }}
      >
        <Box sx={{ p: 1 }}>
          <Typography variant="h5" sx={{ fontWeight: 'bold', mb: 2 }}>
            JSON Editor
          </Typography>
          <Box sx={{ height: '400px', border: '1px solid #ccc', borderRadius: '4px' }}>
            <Editor
              height="100%"
              defaultLanguage="json"
              value={JSON.stringify(dialogData, null, 2)}
              onChange={(value) => {
                try {
                  const parsed = JSON.parse(value);
                  setDialogData(parsed);
                } catch (e) {
                  // Invalid JSON, don't update
                }
              }}
              options={{
                minimap: { enabled: false },
                fontSize: 14,
                lineNumbers: 'on',
                roundedSelection: false,
                scrollBeyondLastLine: false,
                readOnly: false,
                automaticLayout: true,
                formatOnPaste: true,
                formatOnType: true,
              }}
            />
          </Box>
          <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end', mt: 2 }}>
            <Button
              variant="outlined"
              onClick={handleClearDialog}
              sx={{ textTransform: 'none' }}
            >
              Cancel
            </Button>
            <Button
              variant="contained"
              onClick={handleUpdateNodeConfig}
              sx={{ textTransform: 'none' }}
            >
              Update Configuration
            </Button>
          </Box>
        </Box>
      </DialogComponent>
    );
  };

  const renderPlaybookConfigsDialog = () => {
    return (
      <DialogComponent
        open={!!dialogType}
        onClose={handleClearDialog}
        paperProps={{
          maxWidth: 500,
          sx: { borderRadius: 2 }
        }}
      >
        <Box sx={{ p: 1 }}>
          <Typography variant="h5" sx={{ fontWeight: 'bold', mb: 2 }}>
            Playbook Configurations
          </Typography>
          {dialogData?.loading ? <Loading text={"Loading playbook configurations"} /> :
            (
              playbookConfigs?.map((item, index) => (
                <Box>
                  <Button variant="text" sx={{ textTransform: "none" }} onClick={() => handleShowYaml(item)}>{item.name}</Button>
                </Box>
              )
              )
            )}
        </Box>
      </DialogComponent>
    )
  }

  const renderPlaybookConfigEditorDialog = () => {
    return (
      <DialogComponent
        open={!!dialogType}
        onClose={handleClearDialog}
        paperProps={{
          maxWidth: 700,
          sx: { borderRadius: 2 }
        }}
      >
        <Box sx={{ p: 1 }}>
          <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 2, color: "primary.main" }}>
            {dialogData?.name}
          </Typography>
          <YamlEditor initialYaml={dialogData?.data} onYamlChange={(yaml) => {
            setDialogData((prev) => ({ ...prev, data: yaml }))
          }} />

          <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end', mt: 2 }}>
            <Button
              variant="outlined"
              onClick={handleClearDialog}
              sx={{ textTransform: 'none' }}
            >
              Cancel
            </Button>
            <Button
              variant="contained"
              onClick={handleUpdatePlaybookConfig}
              sx={{ textTransform: 'none' }}
            >
              Update
            </Button>
          </Box>
        </Box>
      </DialogComponent>
    )
  }

  const renderClusterCacheDialog = () => {
    return (
      <DialogComponent
        open={clusterCacheDialogOpen}
        onClose={() => setClusterCacheDialogOpen(false)}
        paperProps={{ maxWidth: 500 }}
      >
        <Box sx={{ p: 1 }}>
          <Typography variant="h5" sx={{ fontWeight: 'bold', mb: 1 }}>
            Cluster Cache Configuration
          </Typography>
        </Box>
        <Box gap={2} display={"flex"} flexDirection={"column"}>
          {clusterCacheLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
              <CircularProgress />
            </Box>
          ) : (
            <>
              <FormControl sx={{ minWidth: 120 }} fullWidth variant='outlined'>
                <InputLabel>Registry</InputLabel>
                <Select
                  value={selectedCacheRegistry}
                  onChange={(e) => setSelectedCacheRegistry(e.target.value)}
                  label="Registry"
                >
                  {availableRegistries.map((registry) => (
                    <MenuItem key={registry.name} value={registry.name}>
                      {registry.name} ({registry.registry_config_details.registry})
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              
              <TextField
                label="Repository Name"
                onChange={(e) => setCacheRepo(e.target.value)}
                value={cacheRepo}
                helperText="Repository name for storing checkpoint images"
              />
              
              {clusterCache ? (
                <Box sx={{ p: 2, bgcolor: 'grey.100', borderRadius: 1 }}>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Current Configuration:
                  </Typography>
                  <Typography variant="body2">
                    Registry: {clusterCache.registry}
                  </Typography>
                  <Typography variant="body2">
                    Repository: {clusterCache.repo}
                  </Typography>
                </Box>
              ) : (
                <Box sx={{ p: 2, bgcolor: 'warning.light', borderRadius: 1 }}>
                  <Typography variant="body2" color="warning.contrastText">
                    No cluster cache configured for this cluster
                  </Typography>
                </Box>
              )}
              
              <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
                <Button
                  variant="outlined"
                  onClick={() => setClusterCacheDialogOpen(false)}
                  disabled={clusterCacheLoading}
                >
                  Cancel
                </Button>
                {clusterCache ? (
                  <Button
                    variant="contained"
                    onClick={handleUpdateClusterCache}
                    disabled={clusterCacheLoading || !selectedCacheRegistry}
                    startIcon={clusterCacheLoading ? <CircularProgress size={16} /> : <StorageIcon />}
                  >
                    Update Cache
                  </Button>
                ) : (
                  <Button
                    variant="contained"
                    onClick={handleCreateClusterCache}
                    disabled={clusterCacheLoading || !selectedCacheRegistry}
                    startIcon={clusterCacheLoading ? <CircularProgress size={16} /> : <AddIcon />}
                  >
                    Create Cache
                  </Button>
                )}
              </Box>
            </>
          )}
        </Box>
      </DialogComponent>
    )
  }

  const renderDialog = () => {
    if (!dialogType) return

    const dialogComponent = {
      clusterForm: renderClusterForm,
      enableCheckpoint: renderSelectClusterType,
      confirmEnableCheckpoint: renderConfirmEnableCheckpoint,
      deleteCluster: renderDeleteClusterDialog,
      nodeConfig: renderJsonEditorDialog,
      playbookConfigs: renderPlaybookConfigsDialog,
      playbookConfigEditor: renderPlaybookConfigEditorDialog,
    }

    return dialogComponent[dialogType]()
  }

  const statistics = [
    {
      label: "Pods",
      value: stats.total_pods,
      path: "/pods"
    },
    {
      label: "Checkpoints",
      value: stats.total_checkpoints,
      path: "/checkpoints"
    }
  ]

  const renderLoading = () => {
    const loadingText = loading.verification ? "Verifying cluster"
      : loading.enableCheckpointing ? "Enabling Checkpointing"
        : loading.login ? "Logging in to Cluster"
          : loading.installRunC ? "Installing RunC"
            : "Loading";
    return <Loading text={loadingText} />;
  }

  const isLoading = loading.login || loading.verification || loading.enableCheckpointing || loading.installRunC || authLoading

  return (
    <CustomerContainer title={"Cluster Management"} subtitle="Manage your clusters and their configurations">

      {renderDialog()}
      {renderClusterCacheDialog()}
      {isLoading ? renderLoading() : (
        <>
          {!selectedCluster ? (
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
              <CloudIcon sx={{ fontSize: 60, color: 'primary.main', mb: 2 }} />
              <Typography variant="h5" color="primary" sx={{ mb: 2 }}>
                No Cluster Selected
              </Typography>
              <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
                Add or select a cluster to get started with cluster management
              </Typography>
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={() => setDialogType("clusterForm")}
                sx={{ textTransform: 'none' }}
              >
                Add New Cluster
              </Button>
            </Box>
          ) : (
            <Box>
              {/* Cluster Content */}
                <Stack spacing={4}>
                  {/* Cluster Status Section */}
                  <Paper elevation={0} sx={{ p: 3, bgcolor: 'background.paper', borderRadius: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                  <Box>
                    <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                      {selectedCluster.name}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {clusterType === 'openshift' ? 'OpenShift Cluster' : 'Kubernetes Cluster'}
                    </Typography>
                  </Box>
                  <Chip
                    label={kubeAuthenticated ? "Authenticated" : "Authentication Error"}
                    color={kubeAuthenticated ? "success" : "error"}
                    variant="outlined"
                  />
                </Box>
                <Divider sx={{ my: 2 }} />
                <Grid container spacing={3}>
                  {statistics.map((item, index) => (
                    <Grid item xs={12} sm={6} md={4} key={index}>
                      <Card
                        sx={{
                          height: '100%',
                          cursor: 'pointer'
                        }}
                        onClick={() => item.value ? navigate(item.path) : null}
                      >
                        <CardContent>
                          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                            <StorageIcon sx={{ color: 'primary.main', mr: 1 }} />
                            <Typography variant="subtitle1" color="text.secondary">
                              {item.label}
                            </Typography>
                          </Box>
                          <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
                            {statLoading ? (
                              <CircularProgress size={24} />
                            ) : (
                              item.value || 0
                            )}
                          </Typography>
                        </CardContent>
                      </Card>
                    </Grid>
                  ))}
                </Grid>
              </Paper>

              {/* Actions Section */}
              <Paper elevation={0} sx={{ p: 3, bgcolor: 'background.paper', borderRadius: 2 }}>
                <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 3 }}>
                  Cluster Actions
                </Typography>
                <Grid container spacing={2}>
                  {kubeAuthenticated && (
                    <>
                      <Grid item xs={12} sm={6} md={4}>
                        <Button
                          fullWidth
                          variant="outlined"
                          onClick={handleClusterVerification}
                          startIcon={<VerifyIcon />}
                          sx={{ height: 48, textTransform: 'none' }}
                        >
                          Verify Cluster
                        </Button>
                      </Grid>
                      <Grid item xs={12} sm={6} md={4}>
                        <Button
                          fullWidth
                          variant="outlined"
                          onClick={() => setDialogType("enableCheckpoint")}
                          startIcon={<TaskAltIcon />}
                          sx={{ height: 48, textTransform: 'none' }}
                        >
                          Enable Checkpointing
                        </Button>
                      </Grid>
                      <Grid item xs={12} sm={6} md={4}>
                        <Button
                          fullWidth
                          variant="outlined"
                          onClick={handleInstallRunc}
                          startIcon={<InstallIcon />}
                          sx={{ height: 48, textTransform: 'none' }}
                        >
                          Install runc
                        </Button>
                      </Grid>
                      <Grid item xs={12} sm={6} md={4}>
                        <Button
                          fullWidth
                          variant="outlined"
                          onClick={handleShowNodeConfig}
                          startIcon={<PolylineIcon />}
                          sx={{ height: 48, textTransform: 'none' }}
                        >
                          Node Config
                        </Button>
                      </Grid>
                      <Grid item xs={12} sm={6} md={4}>
                        <Button
                          fullWidth
                          variant="outlined"
                          onClick={handleShowClusterCacheConfig}
                          startIcon={<StorageIcon />}
                          sx={{ height: 48, textTransform: 'none' }}
                        >
                          Cluster Cache Config
                        </Button>
                      </Grid>
                      <Grid item xs={12} sm={6} md={4}>
                        <Button
                          fullWidth
                          variant="outlined"
                          onClick={handlePlaybookConfigs}
                          startIcon={<LibraryBooksIcon />}
                          sx={{ height: 48, textTransform: 'none' }}
                        >
                          Playbook Configs
                        </Button>
                      </Grid>
                    </>
                  )}

                  <Grid item xs={12} sm={6} md={4}>
                    <Button
                      fullWidth
                      variant="outlined"
                      color="warning"
                      onClick={handleShowClusterConfig}
                      startIcon={<Edit />}
                      sx={{ height: 48, textTransform: 'none' }}
                    >
                      Edit Cluster Config
                    </Button>
                  </Grid>
                </Grid>
              </Paper>

              {/* Danger Zone */}
              <Paper elevation={0} sx={{ p: 3, bgcolor: 'error.light', borderRadius: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Box>
                    <Typography variant="h6" sx={{ fontWeight: 'bold', color: 'error.contrastText' }}>
                      Danger Zone
                    </Typography>
                    <Typography variant="body2" sx={{ color: 'error.contrastText' }}>
                      Irreversible and destructive actions
                    </Typography>
                  </Box>
                  <Button
                    variant="contained"
                    color="error"
                    onClick={() => setDialogType("deleteCluster")}
                    startIcon={<Delete />}
                    sx={{ textTransform: 'none' }}
                  >
                    Delete Cluster
                  </Button>
                </Box>
              </Paper>
                </Stack>
            </Box>
          )}
        </>
      )}
    </CustomerContainer>
  )
}

export default ClusterScreen;
