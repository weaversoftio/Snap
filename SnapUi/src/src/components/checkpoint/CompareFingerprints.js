import { Box, Button, CircularProgress, Grid, TextField, Typography, Paper, Autocomplete, Chip, IconButton, Tooltip } from "@mui/material"
import { useEffect, useState } from "react";
import { useSnackbar } from 'notistack';
import { checkpointApi } from "../../api/checkpointApi";
import ReactJson from 'react-json-view';
import { Loading } from "../common/loading";
import { CustomerContainer } from "../common/CustomContainer";
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import VisibilityIcon from '@mui/icons-material/Visibility';
import ComponentDiffViewer from "./ComponentDiffViewer";

const CompareFingerprintsScreen = ({ classes }) => {
  const { enqueueSnackbar } = useSnackbar();
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState([])
  const [selectedCheckpoint1, setSelectedCheckpoint1] = useState(null);
  const [selectedCheckpoint2, setSelectedCheckpoint2] = useState(null);
  const [compareResults, setCompareResults] = useState(null);
  const [isActionRunning, setActionRunning] = useState(false);
  const [diffViewerOpen, setDiffViewerOpen] = useState(false);
  const [selectedComponent, setSelectedComponent] = useState(null);

  useEffect(() => {
    handleGetCheckpoints();
  }, [])

  const handleGetCheckpoints = async () => {
    try {
      setLoading(true)
      const result = await checkpointApi.getList()
      setData(result?.checkpoints || [])
    } catch (error) {
      console.error("Checkpoint list error", error.toString())
      enqueueSnackbar("Failed to load checkpoints", { variant: "error" })
    }
    setLoading(false)
  }

  const handleCompare = async () => {
    if (!selectedCheckpoint1 || !selectedCheckpoint2) {
      enqueueSnackbar("Please select both checkpoints to compare", { variant: "warning" })
      return
    }

    if (selectedCheckpoint1.pod_name === selectedCheckpoint2.pod_name && 
        selectedCheckpoint1.checkpoint_name === selectedCheckpoint2.checkpoint_name) {
      enqueueSnackbar("Please select two different checkpoints to compare", { variant: "warning" })
      return
    }

    try {
      setActionRunning(true)
      enqueueSnackbar("Comparing checkpoint fingerprints...", { variant: "info" })

      const checkpoint1_name = selectedCheckpoint1.checkpoint_name.replace(".tar", "")
      const checkpoint2_name = selectedCheckpoint2.checkpoint_name.replace(".tar", "")

      const result = await checkpointApi.compareCheckpointFingerprints({
        pod_name_1: selectedCheckpoint1.pod_name,
        checkpoint_name_1: checkpoint1_name,
        pod_name_2: selectedCheckpoint2.pod_name,
        checkpoint_name_2: checkpoint2_name
      })

      setCompareResults(result)
      const statusMsg = result.are_identical 
        ? "Checkpoints are identical" 
        : `Checkpoints differ in ${result.differences.components_differing?.length || 0} component(s)`
      enqueueSnackbar(statusMsg, { variant: result.are_identical ? "success" : "info" })
    } catch (error) {
      console.error("Failed to compare checkpoints:", error)
      enqueueSnackbar(`Failed to compare checkpoints: ${error.message || 'Unknown error'}`, { variant: "error" })
    }
    setActionRunning(false)
  }

  const filteredData = data.filter(item => item.has_fingerprint)

  return (
    <CustomerContainer title="Compare Fingerprints" subtitle="Compare forensic fingerprints of two checkpoints">
      {loading ? <Loading /> : (
        <Box>
          <Paper elevation={0} sx={{ px: 3, py: 2, bgcolor: 'background.paper', borderRadius: 2, mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Select Checkpoints to Compare
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Select two checkpoints with fingerprints to compare their forensic signatures and identify differences.
            </Typography>

            <Grid container spacing={3}>
              <Grid item xs={12} md={5}>
                <Typography variant="subtitle2" gutterBottom>
                  Checkpoint 1:
                </Typography>
                <Autocomplete
                  options={filteredData}
                  getOptionLabel={(option) => `${option.pod_name} / ${option.checkpoint_name}`}
                  value={selectedCheckpoint1}
                  onChange={(event, newValue) => setSelectedCheckpoint1(newValue)}
                  renderInput={(params) => (
                    <TextField {...params} placeholder="Select first checkpoint" />
                  )}
                  renderOption={(props, option) => (
                    <Box component="li" {...props}>
                      <Box>
                        <Typography variant="body2" fontWeight="bold">{option.checkpoint_name}</Typography>
                        <Typography variant="caption" color="text.secondary">{option.pod_name}</Typography>
                      </Box>
                    </Box>
                  )}
                />
                {selectedCheckpoint1 && (
                  <Box sx={{ mt: 2, p: 2, bgcolor: '#f5f5f5', borderRadius: 1 }}>
                    <Typography variant="caption" color="text.secondary">Pod:</Typography>
                    <Typography variant="body2">{selectedCheckpoint1.pod_name}</Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>Checkpoint:</Typography>
                    <Typography variant="body2">{selectedCheckpoint1.checkpoint_name}</Typography>
                  </Box>
                )}
              </Grid>

              <Grid item xs={12} md={2} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <CompareArrowsIcon sx={{ fontSize: 40, color: 'text.secondary' }} />
              </Grid>

              <Grid item xs={12} md={5}>
                <Typography variant="subtitle2" gutterBottom>
                  Checkpoint 2:
                </Typography>
                <Autocomplete
                  options={filteredData.filter(item => 
                    !(item.pod_name === selectedCheckpoint1?.pod_name && item.checkpoint_name === selectedCheckpoint1?.checkpoint_name)
                  )}
                  getOptionLabel={(option) => `${option.pod_name} / ${option.checkpoint_name}`}
                  value={selectedCheckpoint2}
                  onChange={(event, newValue) => setSelectedCheckpoint2(newValue)}
                  renderInput={(params) => (
                    <TextField {...params} placeholder="Select second checkpoint" />
                  )}
                  renderOption={(props, option) => (
                    <Box component="li" {...props}>
                      <Box>
                        <Typography variant="body2" fontWeight="bold">{option.checkpoint_name}</Typography>
                        <Typography variant="caption" color="text.secondary">{option.pod_name}</Typography>
                      </Box>
                    </Box>
                  )}
                />
                {selectedCheckpoint2 && (
                  <Box sx={{ mt: 2, p: 2, bgcolor: '#f5f5f5', borderRadius: 1 }}>
                    <Typography variant="caption" color="text.secondary">Pod:</Typography>
                    <Typography variant="body2">{selectedCheckpoint2.pod_name}</Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>Checkpoint:</Typography>
                    <Typography variant="body2">{selectedCheckpoint2.checkpoint_name}</Typography>
                  </Box>
                )}
              </Grid>
            </Grid>

            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
              <Button
                variant="contained"
                size="large"
                startIcon={<CompareArrowsIcon />}
                onClick={handleCompare}
                disabled={!selectedCheckpoint1 || !selectedCheckpoint2 || isActionRunning}
              >
                {isActionRunning ? <CircularProgress size={24} /> : "Compare Fingerprints"}
              </Button>
            </Box>

            {filteredData.length < 2 && (
              <Box sx={{ mt: 3, p: 2, bgcolor: '#fff3e0', borderRadius: 1 }}>
                <Typography variant="body2" color="warning.main">
                  At least 2 checkpoints with fingerprints are required for comparison. 
                  Currently {filteredData.length} checkpoint(s) with fingerprints available.
                </Typography>
              </Box>
            )}
          </Paper>

          {compareResults && (
            <Paper elevation={0} sx={{ px: 3, py: 2, bgcolor: 'background.paper', borderRadius: 2 }}>
              <Typography variant="h6" gutterBottom>
                Comparison Results
              </Typography>

              <Box sx={{ mb: 3, p: 2, bgcolor: compareResults.are_identical ? '#e8f5e9' : '#fff3e0', borderRadius: 1 }}>
                <Typography variant="h6" gutterBottom>
                  {compareResults.are_identical ? '✓ Checkpoints are Identical' : '⚠ Checkpoints Differ'}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {compareResults.message}
                </Typography>
              </Box>

              <Grid container spacing={2} sx={{ mb: 3 }}>
                <Grid item xs={12} md={6}>
                  <Paper sx={{ p: 2, bgcolor: '#f5f5f5' }}>
                    <Typography variant="subtitle2" gutterBottom>Checkpoint 1 Fingerprint</Typography>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', wordBreak: 'break-all', fontSize: '0.85rem' }}>
                      {compareResults.checkpoint_1_fingerprint}
                    </Typography>
                  </Paper>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Paper sx={{ p: 2, bgcolor: '#f5f5f5' }}>
                    <Typography variant="subtitle2" gutterBottom>Checkpoint 2 Fingerprint</Typography>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', wordBreak: 'break-all', fontSize: '0.85rem' }}>
                      {compareResults.checkpoint_2_fingerprint}
                    </Typography>
                  </Paper>
                </Grid>
              </Grid>

              {compareResults.differences && (
                <Box>
                  <Typography variant="h6" gutterBottom>
                    Comparison Details
                  </Typography>
                  
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2">
                      <strong>Size Difference:</strong> {compareResults.differences.size_difference_bytes} bytes
                    </Typography>
                    <Typography variant="body2">
                      <strong>Checkpoint 1 Size:</strong> {compareResults.differences.size_1_bytes} bytes
                    </Typography>
                    <Typography variant="body2">
                      <strong>Checkpoint 2 Size:</strong> {compareResults.differences.size_2_bytes} bytes
                    </Typography>
                  </Box>

                  {/* Summary Statistics */}
                  {compareResults.differences.total_components !== undefined && (
                    <Box sx={{ mb: 3, p: 2, bgcolor: '#f5f5f5', borderRadius: 1 }}>
                      <Typography variant="subtitle2" gutterBottom>
                        Component Summary
                      </Typography>
                      <Grid container spacing={2}>
                        <Grid item xs={12} sm={4}>
                          <Typography variant="body2" color="text.secondary">Total Components:</Typography>
                          <Typography variant="h6">{compareResults.differences.total_components}</Typography>
                        </Grid>
                        <Grid item xs={12} sm={4}>
                          <Typography variant="body2" color="success.main">Matching:</Typography>
                          <Typography variant="h6" color="success.main">
                            {compareResults.differences.matching_count || 0}
                          </Typography>
                        </Grid>
                        <Grid item xs={12} sm={4}>
                          <Typography variant="body2" color="warning.main">Differing:</Typography>
                          <Typography variant="h6" color="warning.main">
                            {compareResults.differences.differing_count || 0}
                          </Typography>
                        </Grid>
                      </Grid>
                    </Box>
                  )}

                  {/* Matching Components */}
                  {compareResults.differences.component_matches && Object.keys(compareResults.differences.component_matches).length > 0 && (
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="subtitle2" gutterBottom color="success.main">
                        ✓ Matching Components ({Object.keys(compareResults.differences.component_matches).length}):
                      </Typography>
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                        {Object.keys(compareResults.differences.component_matches).map((component, index) => {
                          const match = compareResults.differences.component_matches[component];
                          return (
                            <Chip 
                              key={index} 
                              label={`${component}${match.status === 'missing_in_both' ? ' (missing in both)' : ''}`}
                              color="success" 
                              size="small"
                              variant="outlined"
                            />
                          );
                        })}
                      </Box>
                    </Box>
                  )}

                  {/* Differing Components */}
                  {compareResults.differences.components_differing && compareResults.differences.components_differing.length > 0 && (
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="subtitle2" gutterBottom color="warning.main">
                        ⚠ Differing Components ({compareResults.differences.components_differing.length}):
                      </Typography>
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                        {compareResults.differences.components_differing.map((component, index) => {
                          const diff = compareResults.differences.component_differences?.[component];
                          const statusLabel = diff?.status === 'missing_in_one' ? ' (missing in one)' : 
                                             diff?.status === 'different_values' ? ' (different values)' : '';
                          return (
                            <Chip 
                              key={index} 
                              label={component + statusLabel}
                              color="warning" 
                              size="small"
                            />
                          );
                        })}
                      </Box>
                    </Box>
                  )}

                  {/* Detailed Differences Table */}
                  {compareResults.differences.component_differences && Object.keys(compareResults.differences.component_differences).length > 0 && (
                    <Box sx={{ 
                      maxHeight: '60vh', 
                      overflowY: 'auto', 
                      border: '1px solid #ff9800', 
                      borderRadius: 1,
                      p: 2,
                      bgcolor: '#fff3e0'
                    }}>
                      <Typography variant="subtitle2" gutterBottom color="warning.main">
                        Detailed Component Differences:
                      </Typography>
                      <Box sx={{ mt: 2 }}>
                        {Object.entries(compareResults.differences.component_differences).map(([component, diff]) => {
                          const hasContent1 = diff.content_1 !== undefined && diff.content_1 !== null
                          const hasContent2 = diff.content_2 !== undefined && diff.content_2 !== null
                          const hasContent = hasContent1 || hasContent2
                          
                          return (
                            <Box key={component} sx={{ mb: 2, p: 2, bgcolor: 'white', borderRadius: 1, border: '1px solid #e0e0e0' }}>
                              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                                <Typography variant="body2" fontWeight="bold">
                                  {component}
                                </Typography>
                                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                                  {hasContent && (
                                    <Chip 
                                      label="Content Available" 
                                      size="small" 
                                      color="info" 
                                      variant="outlined"
                                      sx={{ fontSize: '0.65rem', height: '20px' }}
                                    />
                                  )}
                                  <Tooltip title="View content diff">
                                    <IconButton
                                      size="small"
                                      onClick={() => {
                                        setSelectedComponent(component)
                                        setDiffViewerOpen(true)
                                      }}
                                      color="primary"
                                    >
                                      <VisibilityIcon fontSize="small" />
                                    </IconButton>
                                  </Tooltip>
                                </Box>
                              </Box>
                              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                                Status: {diff.status || 'unknown'}
                              </Typography>
                              <Grid container spacing={2}>
                                <Grid item xs={12} md={6}>
                                  <Typography variant="caption" color="text.secondary" gutterBottom>
                                    Checkpoint 1 {hasContent1 ? '(Content from cache)' : '(Hash only)'}:
                                  </Typography>
                                  {hasContent1 ? (
                                    <Paper sx={{ p: 1.5, bgcolor: '#f5f5f5', maxHeight: '200px', overflow: 'auto', mt: 0.5 }}>
                                      <ReactJson
                                        src={diff.content_1}
                                        theme="rjv-default"
                                        collapsed={2}
                                        displayDataTypes={false}
                                        displayObjectSize={true}
                                        enableClipboard={true}
                                        style={{ fontSize: '0.7rem' }}
                                      />
                                    </Paper>
                                  ) : (
                                    <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem', wordBreak: 'break-all' }}>
                                      Hash: {diff.checkpoint_1 || '(NULL)'}
                                    </Typography>
                                  )}
                                </Grid>
                                <Grid item xs={12} md={6}>
                                  <Typography variant="caption" color="text.secondary" gutterBottom>
                                    Checkpoint 2 {hasContent2 ? '(Content from cache)' : '(Hash only)'}:
                                  </Typography>
                                  {hasContent2 ? (
                                    <Paper sx={{ p: 1.5, bgcolor: '#f5f5f5', maxHeight: '200px', overflow: 'auto', mt: 0.5 }}>
                                      <ReactJson
                                        src={diff.content_2}
                                        theme="rjv-default"
                                        collapsed={2}
                                        displayDataTypes={false}
                                        displayObjectSize={true}
                                        enableClipboard={true}
                                        style={{ fontSize: '0.7rem' }}
                                      />
                                    </Paper>
                                  ) : (
                                    <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem', wordBreak: 'break-all' }}>
                                      Hash: {diff.checkpoint_2 || '(NULL)'}
                                    </Typography>
                                  )}
                                </Grid>
                              </Grid>
                            </Box>
                          )
                        })}
                      </Box>
                    </Box>
                  )}
                </Box>
              )}
            </Paper>
          )}
        </Box>
      )}

      {/* Component Diff Viewer Dialog */}
      <ComponentDiffViewer
        open={diffViewerOpen}
        onClose={() => {
          setDiffViewerOpen(false)
          setSelectedComponent(null)
        }}
        componentName={selectedComponent}
        podName1={selectedCheckpoint1?.pod_name}
        checkpointName1={selectedCheckpoint1?.checkpoint_name}
        podName2={selectedCheckpoint2?.pod_name}
        checkpointName2={selectedCheckpoint2?.checkpoint_name}
      />
    </CustomerContainer>
  )
}

export default CompareFingerprintsScreen;

