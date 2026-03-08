import { Box, Button, CircularProgress, FormControl, Grid2 as Grid, MenuItem, Select, TextField, Typography, Paper, Autocomplete, Chip, TableContainer, Table, TableHead, TableBody, TableRow, TableCell, TablePagination, useTheme } from "@mui/material"
import ClearIcon from '@mui/icons-material/Clear';
import { useEffect, useMemo, useState, useCallback } from "react";
import { useSnackbar } from 'notistack';
import { checkpointApi } from "../../api/checkpointApi";
import ReactJson from 'react-json-view';
import BeautifulAnalysisResults from "../common/BeautifulAnalysisResults";
import Stack from '@mui/material/Stack';
import IconButton from '@mui/material/IconButton';
import PlayArrowRoundedIcon from '@mui/icons-material/PlayArrowRounded';
import TextSnippetRoundedIcon from '@mui/icons-material/TextSnippetRounded';
import Tooltip from '@mui/material/Tooltip';
import FileUploadIcon from '@mui/icons-material/FileUpload';
import DownloadIcon from '@mui/icons-material/Download';
import DeleteIcon from '@mui/icons-material/Delete';
import FingerprintIcon from '@mui/icons-material/Fingerprint';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import VerifiedUserIcon from '@mui/icons-material/VerifiedUser';
import LinkRoundedIcon from '@mui/icons-material/LinkRounded';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import Checkbox from '@mui/material/Checkbox';
import FormControlLabel from '@mui/material/FormControlLabel';
import { useNavigate } from 'react-router-dom';
import { useDispatch, useSelector } from "react-redux";
import DialogComponent from "../common/Dialog";
import AddCircleIcon from '@mui/icons-material/AddCircle';
import { registryActions } from "../../features/registry/registrySlice";
import { registryApi } from "../../api/registryApi";
import { Loading } from "../common/loading";
import { CustomerContainer } from "../common/CustomContainer";

const CheckpointsScreen = ({ classes }) => {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const { enqueueSnackbar } = useSnackbar();
  const { list: registryList = [], } = useSelector(state => state.registry)
  const [loading, setLoading] = useState(false)
  const [dialogType, setDialogType] = useState("")
  const [data, setData] = useState([])
  const [rowsPerPage, setRowsPerPage] = useState(5)
  const [page, setPage] = useState(0)
  const [currentCheckpoint, setCurrentCheckpoint] = useState(null)
  const [isActionRunning, setActionRunning] = useState(false);
  const [scanResults, setScanResults] = useState(null)

  const [registry, setRegistry] = useState("")

  const [regName, setRegName] = useState("")
  const [regUsername, setRegistryUsername] = useState("")
  const [regPassword, setRegistryPassword] = useState("")

  const [isLogsOpen, setLogsOpen] = useState(false);
  const [logs, setLogs] = useState(null);
  const [fingerprintResults, setFingerprintResults] = useState(null);
  const [verificationResults, setVerificationResults] = useState(null);
  const [keepExtractedFolder, setKeepExtractedFolder] = useState(false);
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

  const handleGetCheckpoints = useCallback(async () => {
    try {
      setLoading(true)
      // const result = JSON.parse(podsData.pods)
      const result = await checkpointApi.getList()
      setData(result?.checkpoints)
    } catch (error) {
      console.error("Checkpoint list error", error.toString())
    }
    setLoading(false)

  }, [])

  const handleGetRegistryList = useCallback(() => {
    dispatch(registryActions.getList())
  }, [dispatch])

  useEffect(() => {
    handleGetCheckpoints();
    handleGetRegistryList();
  }, [handleGetCheckpoints, handleGetRegistryList])

  const handlePushCheckpoint = (pod_name, checkpoint_name) => {
    setDialogType("createAndPushCheckpoint")
    setCurrentCheckpoint({
      "pod_name": pod_name,
      "checkpoint_name": checkpoint_name,
      "checkpoint_config_name": registry
    })
  }

  const handleConfirmPushCheckpoint = async () => {
    const { checkpoint_name } = currentCheckpoint || {}
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
        await handleGetCheckpoints()
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


  const handleRowsPerPageChange = (event) => {
    setRowsPerPage(+event.target.value);
    setPage(0);
  };

  const handlePageChange = (event, newPage) => {
    setPage(newPage);
  };

  //run analysis
  const startCheckpointctl = async (pod_name = "sample_pod", checkpoint_name = "sample_checkpoint") => {
    enqueueSnackbar(`Running analysis for: ${checkpoint_name}`, { variant: "info" });
    try {
      setActionRunning(true);
      setCurrentCheckpoint({ pod_name, checkpoint_name });

      const checkpoint_name_no_ext = checkpoint_name.replace(".tar", "");

      await checkpointApi.runCheckpointctl(pod_name, checkpoint_name_no_ext);
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

  const handleDeleteCheckpoint = (pod_name, checkpoint_name) => {
    setCurrentCheckpoint({ pod_name, checkpoint_name })
    setDialogType("deleteConfirm")
  }

  const handleConfirmDelete = async () => {
    const { pod_name, checkpoint_name } = currentCheckpoint || {}
    if (!pod_name || !checkpoint_name) return

    try {
      setActionRunning(true)
      setDialogType("")
      await checkpointApi.deleteCheckpoint(pod_name, checkpoint_name)
      enqueueSnackbar(`Checkpoint ${checkpoint_name} deleted successfully`, { variant: "success" })
      await handleGetCheckpoints()
    } catch (error) {
      console.error("Failed to delete checkpoint:", error)
      enqueueSnackbar(`Failed to delete checkpoint: ${checkpoint_name}`, { variant: "error" })
    }
    setActionRunning(false)
    setCurrentCheckpoint(null)
  }

  const handleFingerprintCheckpoint = (pod_name, checkpoint_name) => {
    setCurrentCheckpoint({ pod_name, checkpoint_name })
    setDialogType("fingerprintOptions")
  }

  const handleConfirmFingerprint = async () => {
    const { pod_name, checkpoint_name } = currentCheckpoint || {}
    if (!pod_name || !checkpoint_name) return
    
    try {
      setActionRunning(true)
      setDialogType("")
      enqueueSnackbar(`Generating forensic fingerprint for: ${checkpoint_name}`, { variant: "info" })
      
      const checkpoint_name_no_ext = checkpoint_name.replace(".tar", "")
      const result = await checkpointApi.fingerprintCheckpoint({
        pod_name,
        checkpoint_name: checkpoint_name_no_ext,
        keep_extracted_folder: keepExtractedFolder,
        force_regenerate: true  // Force regenerate when user clicks the button
      })
      
      setFingerprintResults(result)
      setDialogType("fingerprint")
      const successMsg = keepExtractedFolder && result.extracted_folder_path
        ? `Forensic fingerprint generated successfully. Extracted folder kept at: ${result.extracted_folder_path}`
        : `Forensic fingerprint generated successfully`
      enqueueSnackbar(successMsg, { variant: "success" })
    } catch (error) {
      console.error("Failed to generate fingerprint:", error)
      enqueueSnackbar(`Failed to generate fingerprint: ${error.message || 'Unknown error'}`, { variant: "error" })
    }
    setActionRunning(false)
  }

  const closeFingerprint = () => {
    setFingerprintResults(null)
    setDialogType("")
    setKeepExtractedFolder(false)
  }

  const handleVerifyFingerprint = async () => {
    const { pod_name, checkpoint_name } = currentCheckpoint || {}
    if (!pod_name || !checkpoint_name) return
    
    try {
      setActionRunning(true)
      setDialogType("")
      enqueueSnackbar(`Verifying fingerprint for: ${checkpoint_name}`, { variant: "info" })
      
      const checkpoint_name_no_ext = checkpoint_name.replace(".tar", "")
      const result = await checkpointApi.verifyFingerprintCheckpoint({
        pod_name,
        checkpoint_name: checkpoint_name_no_ext
      })
      
      setVerificationResults(result)
      setDialogType("verifyFingerprint")
      
      if (result.verification_summary?.verification_passed) {
        enqueueSnackbar("Verification passed: Fingerprint matches checkpoint content", { variant: "success" })
      } else {
        enqueueSnackbar(`Verification failed: ${result.message}`, { variant: "error" })
      }
    } catch (error) {
      console.error("Failed to verify fingerprint:", error)
      enqueueSnackbar(`Failed to verify fingerprint: ${error.message || 'Unknown error'}`, { variant: "error" })
    }
    setActionRunning(false)
  }

  const closeVerification = () => {
    setVerificationResults(null)
    setDialogType("")
  }
  const closeLogs = () => {
    setLogsOpen(false);
    setLogs(null);
  }

  const handleCompareCheckpoints = () => {
    navigate('/checkpoints/compare')
  }

  const handleShowUploadedUrl = (row) => {
    setCurrentCheckpoint({
      pod_name: row.pod_name,
      checkpoint_name: row.checkpoint_name,
      uploaded_image_tag: row.uploaded_image_tag,
      is_uploaded_to_registry: row.is_uploaded_to_registry
    })
    setDialogType("uploadedUrl")
  }

  const handleCopyUploadedUrl = async (uploadedImageTag) => {
    if (!uploadedImageTag) return
    try {
      await navigator.clipboard.writeText(uploadedImageTag)
      enqueueSnackbar("Uploaded checkpoint URL copied to clipboard", { variant: "success" })
    } catch (error) {
      enqueueSnackbar("Failed to copy URL", { variant: "error" })
    }
  }

  const handleClearDialog = () => {
    setDialogType("")
    setRegName("")
    setRegistryUsername("")
    setRegistryPassword("")
    setFingerprintResults(null)
    setVerificationResults(null)
    setKeepExtractedFolder(false)
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

  const renderFingerprintOptions = () => {
    if (!currentCheckpoint) return null
    
    // Check if fingerprint already exists for this checkpoint
    const checkpointItem = data.find(item => 
      item.pod_name === currentCheckpoint?.pod_name && 
      item.checkpoint_name === currentCheckpoint?.checkpoint_name
    )
    const hasExistingFingerprint = checkpointItem?.has_fingerprint || false
    
    return (
      <DialogComponent 
        open={dialogType === "fingerprintOptions"} 
        onClose={handleClearDialog} 
        paperProps={{ maxWidth: 500 }}
      >
        <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Typography variant="h5" gutterBottom>
            {hasExistingFingerprint ? "View/Regenerate Forensic Fingerprint" : "Generate Forensic Fingerprint"}
          </Typography>
          
          {hasExistingFingerprint && (
            <Box sx={{ p: 2, bgcolor: '#e3f2fd', borderRadius: 1 }}>
              <Typography variant="body2" color="info.main">
                A cached fingerprint exists for this checkpoint. You can view it or regenerate a new one.
              </Typography>
            </Box>
          )}
          
          <Box>
            <Typography fontWeight={"bold"} display={"inline"}>
              Pod: <Typography display={"inline"}>{currentCheckpoint?.pod_name}</Typography>
            </Typography>
            <Typography fontWeight={"bold"} display={"inline"} sx={{ display: 'block', mt: 1 }}>
              Checkpoint: <Typography display={"inline"} style={{ wordWrap: "break-word" }}>
                {currentCheckpoint?.checkpoint_name}
              </Typography>
            </Typography>
          </Box>

          <FormControlLabel
            control={
              <Checkbox
                checked={keepExtractedFolder}
                onChange={(e) => setKeepExtractedFolder(e.target.checked)}
                color="primary"
              />
            }
            label="Keep extracted folder for inspection"
          />
          <Typography variant="caption" color="text.secondary">
            If enabled, the extracted checkpoint folder will be kept in /tmp/ for manual inspection. 
            Useful for debugging and detailed analysis.
          </Typography>

          <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end', mt: 2, flexWrap: 'wrap' }}>
            <Button variant="outlined" onClick={handleClearDialog}>
              Cancel
            </Button>
            {hasExistingFingerprint && (
              <>
                <Button 
                  variant="outlined" 
                  color="primary"
                  onClick={async () => {
                    // Load cached fingerprint
                    try {
                      setDialogType("")
                      setActionRunning(true)
                      const checkpoint_name_no_ext = currentCheckpoint.checkpoint_name.replace(".tar", "")
                      const result = await checkpointApi.fingerprintCheckpoint({
                        pod_name: currentCheckpoint.pod_name,
                        checkpoint_name: checkpoint_name_no_ext,
                        keep_extracted_folder: false,
                        force_regenerate: false
                      })
                      setFingerprintResults(result)
                      setDialogType("fingerprint")
                      enqueueSnackbar("Loaded cached fingerprint", { variant: "success" })
                    } catch (error) {
                      enqueueSnackbar(`Failed to load cached fingerprint: ${error.message}`, { variant: "error" })
                    }
                    setActionRunning(false)
                  }}
                  disabled={isActionRunning}
                >
                  View Cached
                </Button>
                <Button 
                  variant="outlined" 
                  color="secondary"
                  onClick={handleVerifyFingerprint}
                  disabled={isActionRunning}
                >
                  Verify
                </Button>
              </>
            )}
            <Button 
              variant="contained" 
              onClick={handleConfirmFingerprint}
              disabled={isActionRunning}
            >
              {hasExistingFingerprint ? "Regenerate" : "Generate Fingerprint"}
            </Button>
          </Box>
        </Box>
      </DialogComponent>
    )
  }

  const handleDownloadResults = () => {
    if (!fingerprintResults) return
    
    const resultsToDownload = {
      checkpoint: currentCheckpoint?.checkpoint_name,
      pod: currentCheckpoint?.pod_name,
      fingerprint: fingerprintResults.fingerprint,
      extracted_folder_path: fingerprintResults.extracted_folder_path,
      components_processed: fingerprintResults.forensic_data?.components_processed,
      components_total: fingerprintResults.forensic_data?.components_total,
      forensic_data: fingerprintResults.forensic_data
    }
    
    const formattedResults = JSON.stringify(resultsToDownload, null, 2)
    const blob = new Blob([formattedResults], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    
    const checkpointName = currentCheckpoint?.checkpoint_name?.replace('.tar', '') || 'checkpoint'
    const podName = currentCheckpoint?.pod_name || 'pod'
    link.download = `fingerprint-results_${podName}_${checkpointName}_${new Date().toISOString().split('T')[0]}.json`
    
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    
    enqueueSnackbar('Results downloaded successfully!', { variant: 'success' })
  }

  const renderFingerprintResults = () => {
    if (!fingerprintResults) return null
    
    return (
      <DialogComponent 
        open={dialogType === "fingerprint"} 
        onClose={closeFingerprint} 
        paperProps={{ maxWidth: 1000, maxHeight: '90vh' }}
      >
        <Box sx={{ p: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h5">
              Forensic Fingerprint Results
            </Typography>
            <Button
              variant="outlined"
              startIcon={<DownloadIcon />}
              onClick={handleDownloadResults}
              size="small"
            >
              Download Results
            </Button>
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Checkpoint: {currentCheckpoint?.checkpoint_name} | Pod: {currentCheckpoint?.pod_name}
          </Typography>
          
          {fingerprintResults.extracted_folder_path && (
            <Box sx={{ mb: 2, p: 2, bgcolor: '#e3f2fd', borderRadius: 1 }}>
              <Typography variant="body2" fontWeight="bold" gutterBottom>
                Extracted Folder Kept:
              </Typography>
              <Typography variant="body2" sx={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>
                {fingerprintResults.extracted_folder_path}
              </Typography>
            </Box>
          )}
          
          {fingerprintResults.forensic_data && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="h6" gutterBottom>
                Fingerprint: {fingerprintResults.fingerprint}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Components Processed: {fingerprintResults.forensic_data.components_processed} / {fingerprintResults.forensic_data.components_total}
              </Typography>
              
              <Box sx={{ 
                maxHeight: '60vh', 
                overflowY: 'auto', 
                border: '1px solid #e0e0e0', 
                borderRadius: 1,
                p: 2,
                bgcolor: '#fafafa'
              }}>
                <ReactJson 
                  src={fingerprintResults.forensic_data} 
                  theme="rjv-default"
                  collapsed={1}
                  displayDataTypes={false}
                  displayObjectSize={true}
                  enableClipboard={true}
                  style={{ fontSize: '14px' }}
                />
              </Box>
            </Box>
          )}
        </Box>
      </DialogComponent>
    )
  }

  const renderVerificationResults = () => {
    if (!verificationResults) return null
    
    const { verification_summary, hash_mismatches, content_mismatches, fingerprint_matches, message } = verificationResults
    const passed = verification_summary?.verification_passed || false
    
    return (
      <DialogComponent 
        open={dialogType === "verifyFingerprint"} 
        onClose={closeVerification} 
        paperProps={{ maxWidth: 1000, maxHeight: '90vh' }}
      >
        <Box sx={{ p: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h5">
              Fingerprint Verification Results
            </Typography>
          </Box>
          
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Checkpoint: {currentCheckpoint?.checkpoint_name} | Pod: {currentCheckpoint?.pod_name}
          </Typography>
          
          {/* Verification Status */}
          <Box sx={{ 
            mb: 2, 
            p: 2, 
            bgcolor: passed ? '#e8f5e9' : '#ffebee', 
            borderRadius: 1,
            border: `2px solid ${passed ? '#4caf50' : '#f44336'}`
          }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <Typography variant="h6" color={passed ? 'success.main' : 'error.main'}>
                {passed ? '✓ Verification Passed' : '✗ Verification Failed'}
              </Typography>
            </Box>
            <Typography variant="body1" fontWeight="bold">
              {message}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              Fingerprint Match: {fingerprint_matches ? 'Yes' : 'No'}
            </Typography>
          </Box>
          
          {/* Summary */}
          {verification_summary && (
            <Box sx={{ mb: 2, p: 2, bgcolor: '#f5f5f5', borderRadius: 1 }}>
              <Typography variant="h6" gutterBottom>
                Verification Summary
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Typography variant="body2">
                    <strong>Total Components:</strong> {verification_summary.total_components}
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="success.main">
                    <strong>Matching Hashes:</strong> {verification_summary.matching_hashes}
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="error.main">
                    <strong>Mismatching Hashes:</strong> {verification_summary.mismatching_hashes}
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="success.main">
                    <strong>Matching Contents:</strong> {verification_summary.matching_contents}
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="error.main">
                    <strong>Mismatching Contents:</strong> {verification_summary.mismatching_contents}
                  </Typography>
                </Grid>
              </Grid>
            </Box>
          )}
          
          {/* Hash Mismatches */}
          {Object.keys(hash_mismatches || {}).length > 0 && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="h6" gutterBottom color="error.main">
                Hash Mismatches ({Object.keys(hash_mismatches).length})
              </Typography>
              <Box sx={{ 
                maxHeight: '30vh', 
                overflowY: 'auto', 
                border: '1px solid #e0e0e0', 
                borderRadius: 1,
                p: 2,
                bgcolor: '#fff3f3'
              }}>
                {Object.entries(hash_mismatches).map(([component, mismatch]) => (
                  <Box key={component} sx={{ mb: 2, p: 1, bgcolor: '#fff', borderRadius: 1 }}>
                    <Typography variant="subtitle2" fontWeight="bold" color="error.main">
                      {component}
                    </Typography>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                      <strong>Stored:</strong> {mismatch.stored_hash || 'None'}
                    </Typography>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                      <strong>New:</strong> {mismatch.new_hash || 'None'}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Status: {mismatch.status}
                    </Typography>
                  </Box>
                ))}
              </Box>
            </Box>
          )}
          
          {/* Content Mismatches */}
          {Object.keys(content_mismatches || {}).length > 0 && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="h6" gutterBottom color="error.main">
                Content Mismatches ({Object.keys(content_mismatches).length})
              </Typography>
              <Box sx={{ 
                maxHeight: '30vh', 
                overflowY: 'auto', 
                border: '1px solid #e0e0e0', 
                borderRadius: 1,
                p: 2,
                bgcolor: '#fff3f3'
              }}>
                {Object.entries(content_mismatches).map(([component, mismatch]) => (
                  <Box key={component} sx={{ mb: 2, p: 1, bgcolor: '#fff', borderRadius: 1 }}>
                    <Typography variant="subtitle2" fontWeight="bold" color="error.main">
                      {component}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Status: {mismatch.status}
                    </Typography>
                    <Box sx={{ mt: 1 }}>
                      <Typography variant="caption" fontWeight="bold">Stored Content:</Typography>
                      <Box sx={{ 
                        maxHeight: '15vh', 
                        overflowY: 'auto',
                        mt: 0.5,
                        p: 1,
                        bgcolor: '#fafafa',
                        borderRadius: 0.5,
                        border: '1px solid #e0e0e0'
                      }}>
                        <ReactJson 
                          src={mismatch.stored_content} 
                          theme="rjv-default"
                          collapsed={2}
                          displayDataTypes={false}
                          displayObjectSize={true}
                          enableClipboard={true}
                          style={{ fontSize: '12px' }}
                        />
                      </Box>
                    </Box>
                    <Box sx={{ mt: 1 }}>
                      <Typography variant="caption" fontWeight="bold">New Content:</Typography>
                      <Box sx={{ 
                        maxHeight: '15vh', 
                        overflowY: 'auto',
                        mt: 0.5,
                        p: 1,
                        bgcolor: '#fafafa',
                        borderRadius: 0.5,
                        border: '1px solid #e0e0e0'
                      }}>
                        <ReactJson 
                          src={mismatch.new_content} 
                          theme="rjv-default"
                          collapsed={2}
                          displayDataTypes={false}
                          displayObjectSize={true}
                          enableClipboard={true}
                          style={{ fontSize: '12px' }}
                        />
                      </Box>
                    </Box>
                  </Box>
                ))}
              </Box>
            </Box>
          )}
          
          {/* Full Results JSON */}
          <Box sx={{ mt: 2 }}>
            <Typography variant="h6" gutterBottom>
              Full Verification Results
            </Typography>
            <Box sx={{ 
              maxHeight: '40vh', 
              overflowY: 'auto', 
              border: '1px solid #e0e0e0', 
              borderRadius: 1,
              p: 2,
              bgcolor: '#fafafa'
            }}>
              <ReactJson 
                src={verificationResults} 
                theme="rjv-default"
                collapsed={1}
                displayDataTypes={false}
                displayObjectSize={true}
                enableClipboard={true}
                style={{ fontSize: '14px' }}
              />
            </Box>
          </Box>
        </Box>
      </DialogComponent>
    )
  }

  const renderDeleteConfirm = () => {
    if (!currentCheckpoint) return null
    
    return (
      <DialogComponent 
        open={dialogType === "deleteConfirm"} 
        onClose={handleClearDialog} 
        paperProps={{ maxWidth: 500 }}
      >
        <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Typography variant="h5" gutterBottom>
            Delete Checkpoint
          </Typography>
          <Typography variant="body1">
            Are you sure you want to delete this checkpoint? This action cannot be undone.
          </Typography>
          <Box sx={{ p: 2, bgcolor: '#fff3cd', borderRadius: 1 }}>
            <Typography variant="body2" fontWeight="bold" gutterBottom>
              Pod: <Typography display="inline">{currentCheckpoint?.pod_name}</Typography>
            </Typography>
            <Typography variant="body2" fontWeight="bold">
              Checkpoint: <Typography display="inline" style={{ wordWrap: "break-word" }}>
                {currentCheckpoint?.checkpoint_name}
              </Typography>
            </Typography>
          </Box>
          <Typography variant="body2" color="text.secondary">
            This will delete the checkpoint file and all associated files (analysis results, fingerprints, etc.).
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end', mt: 2 }}>
            <Button variant="outlined" onClick={handleClearDialog} disabled={isActionRunning}>
              Cancel
            </Button>
            <Button 
              variant="contained" 
              color="error" 
              onClick={handleConfirmDelete}
              disabled={isActionRunning}
              startIcon={isActionRunning ? <CircularProgress size={20} /> : <DeleteIcon />}
            >
              {isActionRunning ? "Deleting..." : "Delete"}
            </Button>
          </Box>
        </Box>
      </DialogComponent>
    )
  }

  const renderUploadedUrlDialog = () => {
    if (dialogType !== "uploadedUrl") return null

    const uploadedImageTag = currentCheckpoint?.uploaded_image_tag
    const isUploaded = !!currentCheckpoint?.is_uploaded_to_registry

    return (
      <DialogComponent
        open
        onClose={handleClearDialog}
        paperProps={{ maxWidth: 700 }}
      >
        <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Typography variant="h5" gutterBottom>
            Uploaded Checkpoint URL
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Pod: {currentCheckpoint?.pod_name} | Checkpoint: {currentCheckpoint?.checkpoint_name}
          </Typography>
          <Box sx={{ p: 2, bgcolor: '#f5f5f5', borderRadius: 1 }}>
            <Typography sx={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>
              {isUploaded && uploadedImageTag
                ? uploadedImageTag
                : "Checkpoint image is not uploaded to registry yet."}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
            <Button variant="outlined" onClick={handleClearDialog}>
              Close
            </Button>
            <Button
              variant="contained"
              startIcon={<ContentCopyIcon />}
              onClick={() => handleCopyUploadedUrl(uploadedImageTag)}
              disabled={!isUploaded || !uploadedImageTag}
            >
              Copy
            </Button>
          </Box>
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
      scanResults: renderScanResults(),
      fingerprintOptions: renderFingerprintOptions(),
      fingerprint: renderFingerprintResults(),
      verifyFingerprint: renderVerificationResults(),
      deleteConfirm: renderDeleteConfirm(),
      uploadedUrl: renderUploadedUrlDialog()
    }
    return dialogContent[dialogType]
  }

  const theme = useTheme()

  const renderStatusChip = (label, color, variant = "outlined") => (
    <Chip 
      label={label} 
      color={color} 
      variant={variant}
      size="small"
      sx={{ 
        fontWeight: 500,
        fontSize: '0.75rem',
        height: '24px'
      }}
    />
  )

  const renderTableRow = (row) => {
    const { pod_name, checkpoint_name, analysis_result, has_fingerprint, uploaded_image_tag, is_uploaded_to_registry } = row
    const isRunning = isActionRunning && currentCheckpoint?.checkpoint_name === checkpoint_name

    return (
      <TableRow
        key={`${pod_name}-${checkpoint_name}`}
        sx={{
          '&:hover': {
            bgcolor: theme.palette.mode === 'dark' ? 'action.hover' : 'grey.50',
            transition: 'background-color 0.2s ease'
          },
          '&:last-child td': { borderBottom: 0 },
          borderBottom: `1px solid ${theme.palette.divider}`
        }}
      >
        <TableCell sx={{ py: 2, px: 3 }}>
          <Typography 
            variant="body2" 
            sx={{ 
              fontWeight: 500,
              color: 'text.primary',
              wordBreak: 'break-word'
            }}
          >
            {checkpoint_name}
          </Typography>
        </TableCell>
        <TableCell sx={{ py: 2, px: 3 }}>
          <Typography 
            variant="body2" 
            sx={{ 
              color: 'text.secondary',
              fontFamily: 'monospace',
              fontSize: '0.875rem'
            }}
          >
            {pod_name}
          </Typography>
        </TableCell>
        <TableCell sx={{ py: 2, px: 3 }}>
          <Box sx={{ display: 'flex', gap: 0.5 }}>
            {analysis_result 
              ? renderStatusChip("Analyzed", "success", "filled")
              : renderStatusChip("Not Analyzed", "default", "outlined")
            }
            {has_fingerprint && renderStatusChip("Fingerprinted", "primary", "filled")}
          </Box>
        </TableCell>
        <TableCell sx={{ py: 2, px: 3 }}>
          {isRunning ? (
            <CircularProgress size={24} />
          ) : (
            <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap', gap: 0.5 }}>
              <Tooltip title={analysis_result ? "Re-analyze" : "Analyze"}>
                <IconButton 
                  aria-label="analyze" 
                  onClick={() => startCheckpointctl(pod_name, checkpoint_name)}
                  size="small"
                  sx={{ 
                    '&:hover': { bgcolor: 'primary.light', color: 'primary.contrastText' }
                  }}
                >
                  <PlayArrowRoundedIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              {analysis_result && (
                <Tooltip title="Show Analysis">
                  <IconButton 
                    aria-label="show analysis" 
                    onClick={() => openLogs(pod_name, checkpoint_name)}
                    size="small"
                    sx={{ 
                      '&:hover': { bgcolor: 'info.light', color: 'info.contrastText' }
                    }}
                  >
                    <TextSnippetRoundedIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              )}
              <Tooltip title={has_fingerprint ? "View/Regenerate Forensic Fingerprint" : "Generate Forensic Fingerprint"}>
                <IconButton 
                  onClick={() => handleFingerprintCheckpoint(pod_name, checkpoint_name)}
                  size="small"
                  sx={{ 
                    '&:hover': { bgcolor: has_fingerprint ? 'primary.light' : 'action.hover' }
                  }}
                >
                  <FingerprintIcon 
                    fontSize="small" 
                    color={has_fingerprint ? "primary" : "inherit"} 
                  />
                </IconButton>
              </Tooltip>
              {has_fingerprint && (
                <Tooltip title="Verify Fingerprint">
                  <IconButton 
                    onClick={async () => {
                      setCurrentCheckpoint({ pod_name, checkpoint_name })
                      try {
                        setActionRunning(true)
                        enqueueSnackbar(`Verifying fingerprint for: ${checkpoint_name}`, { variant: "info" })
                        
                        const checkpoint_name_no_ext = checkpoint_name.replace(".tar", "")
                        const result = await checkpointApi.verifyFingerprintCheckpoint({
                          pod_name,
                          checkpoint_name: checkpoint_name_no_ext
                        })
                        
                        setVerificationResults(result)
                        setDialogType("verifyFingerprint")
                        
                        if (result.verification_summary?.verification_passed) {
                          enqueueSnackbar("Verification passed: Fingerprint matches checkpoint content", { variant: "success" })
                        } else {
                          enqueueSnackbar(`Verification failed: ${result.message}`, { variant: "error" })
                        }
                      } catch (error) {
                        console.error("Failed to verify fingerprint:", error)
                        enqueueSnackbar(`Failed to verify fingerprint: ${error.message || 'Unknown error'}`, { variant: "error" })
                      }
                      setActionRunning(false)
                    }}
                    size="small"
                    disabled={isActionRunning}
                    sx={{ 
                      '&:hover': { bgcolor: 'secondary.light' }
                    }}
                  >
                    <VerifiedUserIcon 
                      fontSize="small" 
                      color="secondary" 
                    />
                  </IconButton>
                </Tooltip>
              )}
              <Tooltip title="Upload Checkpoint">
                <IconButton 
                  onClick={() => handlePushCheckpoint(pod_name, checkpoint_name)}
                  size="small"
                  sx={{ 
                    '&:hover': { bgcolor: 'success.light', color: 'success.contrastText' }
                  }}
                >
                  <FileUploadIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title={is_uploaded_to_registry ? "Uploaded URL (pushed)" : "Not uploaded to registry"}>
                <IconButton
                  onClick={() => handleShowUploadedUrl(row)}
                  size="small"
                  sx={{
                    '&:hover': {
                      bgcolor: is_uploaded_to_registry ? 'success.light' : 'error.light',
                      color: is_uploaded_to_registry ? 'success.contrastText' : 'error.contrastText'
                    }
                  }}
                >
                  <LinkRoundedIcon
                    fontSize="small"
                    color={is_uploaded_to_registry ? "success" : "error"}
                  />
                </IconButton>
              </Tooltip>
              <Tooltip title="Download Checkpoint">
                <IconButton 
                  onClick={() => handleDownloadCheckpoint(pod_name, checkpoint_name)}
                  size="small"
                  sx={{ 
                    '&:hover': { bgcolor: 'info.light', color: 'info.contrastText' }
                  }}
                >
                  <DownloadIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Delete Checkpoint">
                <IconButton 
                  onClick={() => handleDeleteCheckpoint(pod_name, checkpoint_name)}
                  size="small"
                  sx={{ 
                    '&:hover': { bgcolor: 'error.light', color: 'error.contrastText' }
                  }}
                >
                  <DeleteIcon fontSize="small" color="error" />
                </IconButton>
              </Tooltip>
            </Stack>
          )}
        </TableCell>
      </TableRow>
    )
  }

  const renderBeautifiedTable = () => {
    if (!filteredData || filteredData.length === 0) {
      return (
        <Box sx={{ py: 8, textAlign: 'center' }}>
          <Typography variant="body1" color="text.secondary">
            No checkpoints found
          </Typography>
        </Box>
      )
    }

    const paginatedData = filteredData.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)

    return (
      <TableContainer 
        sx={{ 
          borderRadius: 2,
          border: `1px solid ${theme.palette.divider}`,
          overflow: 'hidden'
        }}
      >
        <Table>
          <TableHead>
            <TableRow sx={{ 
              bgcolor: theme.palette.mode === 'dark' ? 'grey.800' : 'grey.100',
              '& th': { 
                fontWeight: 600,
                fontSize: '0.875rem',
                textTransform: 'uppercase',
                letterSpacing: '0.5px',
                color: 'text.secondary',
                py: 2,
                px: 3,
                borderBottom: `2px solid ${theme.palette.divider}`
              } 
            }}>
              <TableCell>Checkpoint</TableCell>
              <TableCell>Pod Name</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {paginatedData.map(renderTableRow)}
          </TableBody>
        </Table>
        {filteredData.length > 0 && (
          <TablePagination
            rowsPerPageOptions={[5, 10, 25, 50]}
            component="div"
            count={filteredData.length}
            rowsPerPage={rowsPerPage}
            page={page}
            onPageChange={handlePageChange}
            onRowsPerPageChange={handleRowsPerPageChange}
            sx={{
              borderTop: `1px solid ${theme.palette.divider}`,
              '& .MuiTablePagination-toolbar': {
                px: 2
              }
            }}
          />
        )}
      </TableContainer>
    )
  }

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
            {renderDialog()}
            <Box sx={{ mt: 2, mb: 2 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6">
                  Search & Filters
                </Typography>
                <Button
                  variant="outlined"
                  startIcon={<CompareArrowsIcon />}
                  onClick={handleCompareCheckpoints}
                  disabled={!data.some(item => item.has_fingerprint) || data.filter(item => item.has_fingerprint).length < 2}
                  size="small"
                >
                  Compare Fingerprints
                </Button>
              </Box>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 2 }}>
                <TextField
                  sx={{ width: '300px', minWidth: '200px' }}
                  size="small"
                  placeholder="Search by pod name or checkpoint name"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
                <Autocomplete
                  sx={{ minWidth: 180 }}
                  size="small"
                  options={["all", ...podOptions]}
                  value={selectedPod}
                  onChange={(event, newValue) => setSelectedPod(newValue || "all")}
                  getOptionLabel={(option) => option === "all" ? "All Pods" : option}
                  renderInput={(params) => (
                    <TextField {...params} placeholder="All Pods" />
                  )}
                  freeSolo
                  selectOnFocus
                  clearOnBlur
                  handleHomeEndKeys
                />
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
            {renderBeautifiedTable()}
          </Paper>
        </>
      )}
    </CustomerContainer>
  )
}

export default CheckpointsScreen;