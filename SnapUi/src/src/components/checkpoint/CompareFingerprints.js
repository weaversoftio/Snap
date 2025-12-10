import { Box, Button, CircularProgress, Grid2 as Grid, TextField, Typography, Paper, Autocomplete, Chip, Tabs, Tab, Badge, Alert, AlertTitle, Accordion, AccordionSummary, AccordionDetails, List, ListItem, ListItemText, ListItemIcon, Divider } from "@mui/material"
import { useEffect, useState, useCallback } from "react";
import { useSnackbar } from 'notistack';
import { checkpointApi } from "../../api/checkpointApi";
import ReactJson from 'react-json-view';
import { Loading } from "../common/loading";
import { CustomerContainer } from "../common/CustomContainer";
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import WarningIcon from '@mui/icons-material/Warning';
import ErrorIcon from '@mui/icons-material/Error';
import InfoIcon from '@mui/icons-material/Info';
import SecurityIcon from '@mui/icons-material/Security';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import FilterListIcon from '@mui/icons-material/FilterList';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';

const CompareFingerprintsScreen = ({ classes }) => {
  const { enqueueSnackbar } = useSnackbar();
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState([])
  const [selectedCheckpoint1, setSelectedCheckpoint1] = useState(null);
  const [selectedCheckpoint2, setSelectedCheckpoint2] = useState(null);
  const [compareResults, setCompareResults] = useState(null);
  const [isActionRunning, setActionRunning] = useState(false);
  const [componentDiffData, setComponentDiffData] = useState({});
  const [loadingDiffs, setLoadingDiffs] = useState({});
  const [riskFilter, setRiskFilter] = useState('all'); // all, critical, high, medium, low, info
  const [categoryFilter, setCategoryFilter] = useState('all'); // all, security, operational, performance, configuration
  const [expandedComponents, setExpandedComponents] = useState(new Set());

  const handleGetCheckpoints = useCallback(async () => {
    try {
      setLoading(true)
      const result = await checkpointApi.getList()
      setData(result?.checkpoints || [])
    } catch (error) {
      console.error("Checkpoint list error", error.toString())
      enqueueSnackbar("Failed to load checkpoints", { variant: "error" })
    }
    setLoading(false)
  }, [enqueueSnackbar])

  useEffect(() => {
    handleGetCheckpoints();
  }, [handleGetCheckpoints])

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

  // Get risk color and icon
  const getRiskColor = (level) => {
    switch(level) {
      case 'critical': return '#d32f2f';
      case 'high': return '#f57c00';
      case 'medium': return '#fbc02d';
      case 'low': return '#388e3c';
      default: return '#616161';
    }
  }

  const getRiskIcon = (level) => {
    switch(level) {
      case 'critical': return <ErrorIcon sx={{ fontSize: 18 }} />;
      case 'high': return <WarningIcon sx={{ fontSize: 18 }} />;
      case 'medium': return <WarningIcon sx={{ fontSize: 18 }} />;
      case 'low': return <InfoIcon sx={{ fontSize: 18 }} />;
      default: return <InfoIcon sx={{ fontSize: 18 }} />;
    }
  }

  // Filter components by risk and category
  const getFilteredComponents = () => {
    if (!compareResults?.differences?.component_differences) return []
    
    const components = Object.entries(compareResults.differences.component_differences)
    
    return components.filter(([component, diff]) => {
      const risk = diff.risk_assessment
      if (!risk) return riskFilter === 'all'
      
      // Risk level filter
      if (riskFilter !== 'all' && risk.risk_level !== riskFilter) return false
      
      // Category filter
      if (categoryFilter !== 'all' && risk.risk_category !== categoryFilter) return false
      
      return true
    }).sort(([compA, diffA], [compB, diffB]) => {
      // Sort by risk score (highest first)
      const scoreA = diffA.risk_assessment?.risk_score || 0
      const scoreB = diffB.risk_assessment?.risk_score || 0
      return scoreB - scoreA
    })
  }

  // Jump to component
  const scrollToComponent = (componentName) => {
    const element = document.getElementById(`component-${componentName}`)
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' })
      // Expand the component
      setExpandedComponents(prev => new Set([...prev, componentName]))
    }
  }

  // Load component diff when compare results are available
  useEffect(() => {
    if (!compareResults || !selectedCheckpoint1 || !selectedCheckpoint2) return

    const loadComponentDiffs = async () => {
      const componentDiffs = compareResults.differences?.component_differences || {}
      const componentsToLoad = Object.keys(componentDiffs)

      for (const component of componentsToLoad) {
        const diff = componentDiffs[component]
        const hasContent1 = diff.content_1 !== undefined && diff.content_1 !== null
        const hasContent2 = diff.content_2 !== undefined && diff.content_2 !== null
        
        // Only load if we don't have content from cache
        if (!hasContent1 || !hasContent2) {
          try {
            setLoadingDiffs(prev => ({ ...prev, [component]: true }))
            const checkpoint1_clean = selectedCheckpoint1.checkpoint_name.replace(".tar", "")
            const checkpoint2_clean = selectedCheckpoint2.checkpoint_name.replace(".tar", "")
            
            const result = await checkpointApi.getComponentDiff(
              selectedCheckpoint1.pod_name,
              checkpoint1_clean,
              selectedCheckpoint2.pod_name,
              checkpoint2_clean,
              component
            )
            
            setComponentDiffData(prev => ({ ...prev, [component]: result }))
          } catch (error) {
            console.error(`Failed to load diff for ${component}:`, error)
          } finally {
            setLoadingDiffs(prev => ({ ...prev, [component]: false }))
          }
        }
      }
    }

    loadComponentDiffs()
  }, [compareResults, selectedCheckpoint1, selectedCheckpoint2])

  // Convert content to string format for comparison
  const getContentAsString = (content) => {
    if (content === null || content === undefined) return ''
    if (typeof content === 'string') return content
    try {
      return JSON.stringify(content, null, 2)
    } catch {
      return String(content)
    }
  }

  // Simple line-by-line diff algorithm
  const computeSideBySideDiff = (content1, content2) => {
    const str1 = getContentAsString(content1)
    const str2 = getContentAsString(content2)
    
    const lines1 = str1.split('\n')
    const lines2 = str2.split('\n')
    
    const maxLines = Math.max(lines1.length, lines2.length)
    const diff = []
    
    for (let i = 0; i < maxLines; i++) {
      const line1 = lines1[i]
      const line2 = lines2[i]
      
      if (line1 === undefined) {
        diff.push({ type: 'added', left: null, right: line2, lineNum: i + 1 })
      } else if (line2 === undefined) {
        diff.push({ type: 'removed', left: line1, right: null, lineNum: i + 1 })
      } else if (line1 === line2) {
        diff.push({ type: 'unchanged', left: line1, right: line2, lineNum: i + 1 })
      } else {
        diff.push({ type: 'modified', left: line1, right: line2, lineNum: i + 1 })
      }
    }
    
    return diff
  }

  const renderComponentDiff = (component, diff) => {
    // Get diff data if available, otherwise use cached content
    const diffData = componentDiffData[component]
    const isLoading = loadingDiffs[component]
    
    const hasContent1 = diff.content_1 !== undefined && diff.content_1 !== null
    const hasContent2 = diff.content_2 !== undefined && diff.content_2 !== null
    
    // Use diff data if available, otherwise fall back to cached content
    const content1 = diffData?.content_1 ?? diff.content_1
    const content2 = diffData?.content_2 ?? diff.content_2
    
    // Content detection: use has_content flag if available, otherwise check if content exists and is not an error dict
    const hasValidContent = (content, hasContentFlag) => {
      // If flag is explicitly set, use it
      if (hasContentFlag === true) return true
      if (hasContentFlag === false) return false
      // Otherwise, check if content exists and is not an error dict
      if (content === null || content === undefined) return false
      // Empty objects/arrays should be considered as having content (they exist, just empty)
      if (typeof content === 'object' && 'error' in content && Object.keys(content).length === 1) return false
      return true
    }
    
    const finalHasContent1 = diffData 
      ? hasValidContent(diffData.content_1, diffData.has_content_1)
      : hasValidContent(diff.content_1, diff.content_1 !== undefined && diff.content_1 !== null)
    const finalHasContent2 = diffData 
      ? hasValidContent(diffData.content_2, diffData.has_content_2)
      : hasValidContent(diff.content_2, diff.content_2 !== undefined && diff.content_2 !== null)

    if (isLoading) {
      return (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', p: 3 }}>
          <CircularProgress size={24} />
          <Typography variant="body2" sx={{ ml: 2 }}>Loading diff...</Typography>
        </Box>
      )
    }

    if (!finalHasContent1 && !finalHasContent2) {
      return (
        <Box sx={{ p: 2, textAlign: 'center', bgcolor: '#f5f5f5', borderRadius: 1 }}>
          <Typography variant="body2" color="text.secondary">
            Component is missing in both checkpoints
          </Typography>
        </Box>
      )
    }

    if (!finalHasContent1) {
      return (
        <Box sx={{ p: 2 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Component is missing in checkpoint 1
          </Typography>
          <Paper sx={{ p: 2, bgcolor: '#f5f5f5', maxHeight: '400px', overflow: 'auto' }}>
            <Typography variant="caption" color="text.secondary" gutterBottom>
              Checkpoint 2:
            </Typography>
            {typeof content2 === 'object' && content2 !== null ? (
              <ReactJson
                src={content2}
                theme="rjv-default"
                collapsed={1}
                displayDataTypes={false}
                displayObjectSize={true}
                enableClipboard={true}
                style={{ fontSize: '0.75rem' }}
              />
            ) : (
              <Box sx={{ fontFamily: 'monospace', fontSize: '0.75rem', whiteSpace: 'pre-wrap' }}>
                {diffData?.canonical_2 || JSON.stringify(content2, null, 2)}
              </Box>
            )}
          </Paper>
        </Box>
      )
    }

    if (!finalHasContent2) {
      return (
        <Box sx={{ p: 2 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Component is missing in checkpoint 2
          </Typography>
          <Paper sx={{ p: 2, bgcolor: '#f5f5f5', maxHeight: '400px', overflow: 'auto' }}>
            <Typography variant="caption" color="text.secondary" gutterBottom>
              Checkpoint 1:
            </Typography>
            {typeof content1 === 'object' && content1 !== null ? (
              <ReactJson
                src={content1}
                theme="rjv-default"
                collapsed={1}
                displayDataTypes={false}
                displayObjectSize={true}
                enableClipboard={true}
                style={{ fontSize: '0.75rem' }}
              />
            ) : (
              <Box sx={{ fontFamily: 'monospace', fontSize: '0.75rem', whiteSpace: 'pre-wrap' }}>
                {diffData?.canonical_1 || JSON.stringify(content1, null, 2)}
              </Box>
            )}
          </Paper>
        </Box>
      )
    }

    const diffLines = computeSideBySideDiff(content1, content2)

    return (
      <Box sx={{ border: '1px solid #e0e0e0', borderRadius: 1, overflow: 'hidden' }}>
        <Box sx={{ display: 'flex' }}>
          {/* Left side - Checkpoint 1 */}
          <Box sx={{ flex: 1, borderRight: '1px solid #e0e0e0' }}>
            <Box sx={{ 
              bgcolor: '#f5f5f5', 
              p: 1, 
              borderBottom: '1px solid #e0e0e0',
              position: 'sticky',
              top: 0,
              zIndex: 1
            }}>
              <Typography variant="caption" fontWeight="bold">
                Checkpoint 1
              </Typography>
            </Box>
            <Box sx={{ 
              maxHeight: '400px', 
              overflow: 'auto',
              fontFamily: 'monospace',
              fontSize: '0.8rem'
            }}>
              {diffLines.map((diffLine, index) => {
                let bgColor = 'transparent'
                if (diffLine.type === 'removed') bgColor = '#ffebee'
                else if (diffLine.type === 'modified') bgColor = '#fff3e0'
                
                return (
                  <Box
                    key={index}
                    sx={{
                      display: 'flex',
                      bgcolor: bgColor,
                      borderLeft: diffLine.type === 'removed' ? '3px solid #f44336' : 
                                 diffLine.type === 'modified' ? '3px solid #ff9800' : 'none',
                      minHeight: '24px',
                      alignItems: 'flex-start'
                    }}
                  >
                    <Box
                      sx={{
                        minWidth: '50px',
                        px: 1,
                        py: 0.5,
                        color: 'text.secondary',
                        textAlign: 'right',
                        userSelect: 'none',
                        bgcolor: '#fafafa',
                        borderRight: '1px solid #e0e0e0'
                      }}
                    >
                      {diffLine.left !== null ? diffLine.lineNum : ''}
                    </Box>
                    <Box sx={{ 
                      flex: 1, 
                      px: 1, 
                      py: 0.5,
                      wordBreak: 'break-all',
                      whiteSpace: 'pre-wrap'
                    }}>
                      {diffLine.left !== null ? diffLine.left : <span style={{ color: '#999' }}>—</span>}
                    </Box>
                  </Box>
                )
              })}
            </Box>
          </Box>

          {/* Right side - Checkpoint 2 */}
          <Box sx={{ flex: 1 }}>
            <Box sx={{ 
              bgcolor: '#f5f5f5', 
              p: 1, 
              borderBottom: '1px solid #e0e0e0',
              position: 'sticky',
              top: 0,
              zIndex: 1
            }}>
              <Typography variant="caption" fontWeight="bold">
                Checkpoint 2
              </Typography>
            </Box>
            <Box sx={{ 
              maxHeight: '400px', 
              overflow: 'auto',
              fontFamily: 'monospace',
              fontSize: '0.8rem'
            }}>
              {diffLines.map((diffLine, index) => {
                let bgColor = 'transparent'
                if (diffLine.type === 'added') bgColor = '#e8f5e9'
                else if (diffLine.type === 'modified') bgColor = '#fff3e0'
                
                return (
                  <Box
                    key={index}
                    sx={{
                      display: 'flex',
                      bgcolor: bgColor,
                      borderLeft: diffLine.type === 'added' ? '3px solid #4caf50' : 
                                 diffLine.type === 'modified' ? '3px solid #ff9800' : 'none',
                      minHeight: '24px',
                      alignItems: 'flex-start'
                    }}
                  >
                    <Box
                      sx={{
                        minWidth: '50px',
                        px: 1,
                        py: 0.5,
                        color: 'text.secondary',
                        textAlign: 'right',
                        userSelect: 'none',
                        bgcolor: '#fafafa',
                        borderRight: '1px solid #e0e0e0'
                      }}
                    >
                      {diffLine.right !== null ? diffLine.lineNum : ''}
                    </Box>
                    <Box sx={{ 
                      flex: 1, 
                      px: 1, 
                      py: 0.5,
                      wordBreak: 'break-all',
                      whiteSpace: 'pre-wrap'
                    }}>
                      {diffLine.right !== null ? diffLine.right : <span style={{ color: '#999' }}>—</span>}
                    </Box>
                  </Box>
                )
              })}
            </Box>
          </Box>
        </Box>
        
        {/* Legend */}
        {finalHasContent1 && finalHasContent2 && (
          <Box sx={{ p: 1.5, bgcolor: '#f5f5f5', borderTop: '1px solid #e0e0e0' }}>
            <Typography variant="caption" fontWeight="bold" gutterBottom sx={{ display: 'block' }}>
              Legend:
            </Typography>
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mt: 0.5 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Box sx={{ width: 16, height: 16, bgcolor: '#ffebee', borderLeft: '3px solid #f44336' }} />
                <Typography variant="caption">Removed (only in Checkpoint 1)</Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Box sx={{ width: 16, height: 16, bgcolor: '#e8f5e9', borderLeft: '3px solid #4caf50' }} />
                <Typography variant="caption">Added (only in Checkpoint 2)</Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Box sx={{ width: 16, height: 16, bgcolor: '#fff3e0', borderLeft: '3px solid #ff9800' }} />
                <Typography variant="caption">Modified (different in both)</Typography>
              </Box>
            </Box>
          </Box>
        )}
      </Box>
    )
  }

  return (
    <CustomerContainer title="Compare Fingerprints" subtitle="Compare forensic fingerprints of two checkpoints">
      {loading ? <Loading /> : (
        <Box>
          <Paper elevation={0} sx={{ px: 3, py: 2.5, bgcolor: 'background.paper', borderRadius: 2, mb: compareResults ? 2 : 3 }}>
            <Grid container spacing={2} alignItems="center">
              <Grid size={{ xs: 12, sm: 5 }}>
                <Autocomplete
                  options={filteredData}
                  getOptionLabel={(option) => `${option.pod_name} / ${option.checkpoint_name}`}
                  value={selectedCheckpoint1}
                  onChange={(event, newValue) => setSelectedCheckpoint1(newValue)}
                  renderInput={(params) => (
                    <TextField {...params} placeholder="Select Checkpoint 1" size="small" fullWidth />
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
              </Grid>

              <Grid size={{ xs: 12, sm: 2 }} sx={{ display: { xs: 'none', sm: 'flex' }, alignItems: 'center', justifyContent: 'center' }}>
                <CompareArrowsIcon sx={{ fontSize: 28, color: 'text.secondary' }} />
              </Grid>

              <Grid size={{ xs: 12, sm: 5 }}>
                <Autocomplete
                  options={filteredData.filter(item => 
                    !(item.pod_name === selectedCheckpoint1?.pod_name && item.checkpoint_name === selectedCheckpoint1?.checkpoint_name)
                  )}
                  getOptionLabel={(option) => `${option.pod_name} / ${option.checkpoint_name}`}
                  value={selectedCheckpoint2}
                  onChange={(event, newValue) => setSelectedCheckpoint2(newValue)}
                  renderInput={(params) => (
                    <TextField {...params} placeholder="Select Checkpoint 2" size="small" fullWidth />
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
              </Grid>
            </Grid>

            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
              <Button
                variant="contained"
                size="large"
                startIcon={!isActionRunning && <CompareArrowsIcon />}
                onClick={handleCompare}
                disabled={!selectedCheckpoint1 || !selectedCheckpoint2 || isActionRunning}
                sx={{ 
                  minWidth: 150,
                  px: 3,
                  py: 1.5
                }}
              >
                {isActionRunning ? <CircularProgress size={20} color="inherit" /> : "COMPARE"}
              </Button>
            </Box>

            {filteredData.length < 2 && (
              <Box sx={{ mt: 2, p: 1.5, bgcolor: '#fff3e0', borderRadius: 1 }}>
                <Typography variant="body2" color="warning.main" sx={{ fontSize: '0.875rem' }}>
                  At least 2 checkpoints with fingerprints are required. Currently {filteredData.length} available.
                </Typography>
              </Box>
            )}
          </Paper>

          {compareResults && (
            <Box>
              {/* Risk Summary Alert */}
              {compareResults.differences?.risk_summary && (
                <Alert 
                  severity={
                    compareResults.differences.risk_summary.critical > 0 ? 'error' :
                    compareResults.differences.risk_summary.high > 0 ? 'warning' :
                    compareResults.differences.risk_summary.medium > 0 ? 'info' : 'success'
                  }
                  sx={{ mb: 2 }}
                  icon={<SecurityIcon />}
                >
                  <AlertTitle>Risk Assessment</AlertTitle>
                  <Box sx={{ display: 'flex', gap: 3, mt: 1, flexWrap: 'wrap' }}>
                    {compareResults.differences.risk_summary.critical > 0 && (
                      <Chip 
                        icon={<ErrorIcon />}
                        label={`${compareResults.differences.risk_summary.critical} Critical`}
                        color="error"
                        size="small"
                      />
                    )}
                    {compareResults.differences.risk_summary.high > 0 && (
                      <Chip 
                        icon={<WarningIcon />}
                        label={`${compareResults.differences.risk_summary.high} High`}
                        color="warning"
                        size="small"
                      />
                    )}
                    {compareResults.differences.risk_summary.medium > 0 && (
                      <Chip 
                        label={`${compareResults.differences.risk_summary.medium} Medium`}
                        color="default"
                        size="small"
                      />
                    )}
                    {compareResults.differences.risk_summary.low > 0 && (
                      <Chip 
                        label={`${compareResults.differences.risk_summary.low} Low`}
                        color="default"
                        size="small"
                        variant="outlined"
                      />
                    )}
                    <Typography variant="caption" color="text.secondary" sx={{ alignSelf: 'center' }}>
                      {compareResults.differences.risk_summary.total_findings} total findings
                    </Typography>
                  </Box>
                </Alert>
              )}

              {/* Quick Findings Navigation */}
              {compareResults.differences?.findings && compareResults.differences.findings.length > 0 && (
                <Paper sx={{ mb: 2, p: 2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
                    <FilterListIcon sx={{ mr: 1, color: 'text.secondary' }} />
                    <Typography variant="subtitle2" fontWeight="bold">
                      Critical Findings - Quick Navigation
                    </Typography>
                  </Box>
                  <List dense sx={{ maxHeight: '200px', overflow: 'auto' }}>
                    {compareResults.differences.findings.slice(0, 10).map((finding, idx) => (
                      <ListItem 
                        key={idx}
                        button
                        onClick={() => scrollToComponent(finding.component)}
                        sx={{ 
                          borderRadius: 1,
                          mb: 0.5,
                          '&:hover': { bgcolor: 'action.hover' }
                        }}
                      >
                        <ListItemIcon sx={{ minWidth: 36 }}>
                          <Box sx={{ color: getRiskColor(finding.severity) }}>
                            {getRiskIcon(finding.severity)}
                          </Box>
                        </ListItemIcon>
                        <ListItemText
                          primary={
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <Typography variant="body2" fontWeight="medium">
                                {finding.component}
                              </Typography>
                              <Chip 
                                label={finding.severity}
                                size="small"
                                sx={{ 
                                  height: '18px',
                                  fontSize: '0.65rem',
                                  bgcolor: getRiskColor(finding.severity),
                                  color: 'white'
                                }}
                              />
                            </Box>
                          }
                          secondary={finding.message}
                        />
                        <NavigateNextIcon sx={{ color: 'text.secondary', fontSize: 18 }} />
                      </ListItem>
                    ))}
                  </List>
                </Paper>
              )}

              {/* Compact Summary Header */}
              <Box sx={{ mb: 2, p: 1.5, bgcolor: compareResults.are_identical ? '#e8f5e9' : '#fff3e0', borderRadius: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1 }}>
                <Box>
                  <Typography variant="subtitle1" fontWeight="bold">
                    {compareResults.are_identical ? '✓ Identical' : '⚠ Differ'}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {compareResults.message}
                  </Typography>
                </Box>
                {compareResults.differences?.total_components !== undefined && (
                  <Box sx={{ display: 'flex', gap: 2 }}>
                    <Box sx={{ textAlign: 'center' }}>
                      <Typography variant="caption" color="text.secondary">Total</Typography>
                      <Typography variant="body2" fontWeight="bold">{compareResults.differences.total_components}</Typography>
                    </Box>
                    <Box sx={{ textAlign: 'center' }}>
                      <Typography variant="caption" color="success.main">Match</Typography>
                      <Typography variant="body2" fontWeight="bold" color="success.main">
                        {compareResults.differences.matching_count || 0}
                      </Typography>
                    </Box>
                    <Box sx={{ textAlign: 'center' }}>
                      <Typography variant="caption" color="warning.main">Differ</Typography>
                      <Typography variant="body2" fontWeight="bold" color="warning.main">
                        {compareResults.differences.differing_count || 0}
                      </Typography>
                    </Box>
                  </Box>
                )}
              </Box>

              {/* Risk Filters */}
              {compareResults.differences?.component_differences && Object.keys(compareResults.differences.component_differences).length > 0 && (
                <Paper sx={{ mb: 2, p: 1.5 }}>
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
                    <Typography variant="caption" fontWeight="bold" sx={{ mr: 1 }}>Filter by Risk:</Typography>
                    {['all', 'critical', 'high', 'medium', 'low', 'info'].map(level => (
                      <Chip
                        key={level}
                        label={level.charAt(0).toUpperCase() + level.slice(1)}
                        onClick={() => setRiskFilter(level)}
                        color={riskFilter === level ? 'primary' : 'default'}
                        variant={riskFilter === level ? 'filled' : 'outlined'}
                        size="small"
                        sx={{ 
                          cursor: 'pointer',
                          ...(riskFilter === level && level !== 'all' && {
                            bgcolor: getRiskColor(level),
                            color: 'white',
                            '&:hover': { bgcolor: getRiskColor(level) }
                          })
                        }}
                      />
                    ))}
                    <Divider orientation="vertical" flexItem sx={{ mx: 1 }} />
                    <Typography variant="caption" fontWeight="bold" sx={{ mr: 1 }}>Category:</Typography>
                    {['all', 'security', 'operational', 'performance', 'configuration'].map(cat => (
                      <Chip
                        key={cat}
                        label={cat.charAt(0).toUpperCase() + cat.slice(1)}
                        onClick={() => setCategoryFilter(cat)}
                        color={categoryFilter === cat ? 'primary' : 'default'}
                        variant={categoryFilter === cat ? 'filled' : 'outlined'}
                        size="small"
                        sx={{ cursor: 'pointer' }}
                      />
                    ))}
                  </Box>
                </Paper>
              )}

              {compareResults.differences && (
                <Box>
                  {/* Matching Components - Collapsed */}
                  {compareResults.differences.component_matches && Object.keys(compareResults.differences.component_matches).length > 0 && (
                    <Box sx={{ mb: 1.5 }}>
                      <Typography variant="caption" color="success.main" sx={{ fontWeight: 'bold' }}>
                        ✓ Matching ({Object.keys(compareResults.differences.component_matches).length}):
                      </Typography>
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
                        {Object.keys(compareResults.differences.component_matches).slice(0, 10).map((component, index) => (
                          <Chip 
                            key={index} 
                            label={component}
                            color="success" 
                            size="small"
                            variant="outlined"
                            sx={{ height: '20px', fontSize: '0.7rem' }}
                          />
                        ))}
                        {Object.keys(compareResults.differences.component_matches).length > 10 && (
                          <Chip 
                            label={`+${Object.keys(compareResults.differences.component_matches).length - 10} more`}
                            size="small"
                            variant="outlined"
                            sx={{ height: '20px', fontSize: '0.7rem' }}
                          />
                        )}
                      </Box>
                    </Box>
                  )}

                  {/* Differing Components - Collapsed */}
                  {compareResults.differences.components_differing && compareResults.differences.components_differing.length > 0 && (
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="caption" color="warning.main" sx={{ fontWeight: 'bold' }}>
                        ⚠ Differing ({compareResults.differences.components_differing.length}):
                      </Typography>
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
                        {compareResults.differences.components_differing.map((component, index) => (
                          <Chip 
                            key={index} 
                            label={component}
                            color="warning" 
                            size="small"
                            sx={{ height: '20px', fontSize: '0.7rem' }}
                          />
                        ))}
                      </Box>
                    </Box>
                  )}

                  {/* Detailed Differences - Main Focus */}
                  {getFilteredComponents().length > 0 && (
                    <Box>
                      <Typography variant="h6" gutterBottom sx={{ mb: 2, fontSize: '1.1rem' }}>
                        Component Differences
                        {riskFilter !== 'all' || categoryFilter !== 'all' ? (
                          <Chip 
                            label={`${getFilteredComponents().length} shown`}
                            size="small"
                            sx={{ ml: 1 }}
                          />
                        ) : null}
                      </Typography>
                      <Box sx={{ mt: 1 }}>
                        {getFilteredComponents().map(([component, diff]) => {
                          const hasContent1 = diff.content_1 !== undefined && diff.content_1 !== null
                          const hasContent2 = diff.content_2 !== undefined && diff.content_2 !== null
                          const hasContent = hasContent1 || hasContent2
                          const risk = diff.risk_assessment
                          const isExpanded = expandedComponents.has(component)
                          
                          return (
                            <Accordion 
                              key={component}
                              id={`component-${component}`}
                              expanded={isExpanded}
                              onChange={(e, expanded) => {
                                setExpandedComponents(prev => {
                                  const next = new Set(prev)
                                  if (expanded) {
                                    next.add(component)
                                  } else {
                                    next.delete(component)
                                  }
                                  return next
                                })
                              }}
                              sx={{ 
                                mb: 2.5,
                                border: `1px solid ${risk ? getRiskColor(risk.risk_level) : '#e0e0e0'}`,
                                borderRadius: 1,
                                '&:before': { display: 'none' },
                                boxShadow: risk && risk.risk_level === 'critical' ? `0 0 8px ${getRiskColor(risk.risk_level)}40` : 'none'
                              }}
                            >
                              <AccordionSummary
                                expandIcon={<ExpandMoreIcon />}
                                sx={{ 
                                  bgcolor: risk ? `${getRiskColor(risk.risk_level)}10` : '#f5f5f5',
                                  borderBottom: '1px solid #e0e0e0',
                                  '&:hover': { bgcolor: risk ? `${getRiskColor(risk.risk_level)}15` : '#fafafa' }
                                }}
                              >
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%', pr: 2 }}>
                                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                                    {risk && (
                                      <Box sx={{ color: getRiskColor(risk.risk_level) }}>
                                        {getRiskIcon(risk.risk_level)}
                                      </Box>
                                    )}
                                    <Typography variant="subtitle1" fontWeight="bold">
                                      {component}
                                    </Typography>
                                    {risk && (
                                      <>
                                        <Chip 
                                          label={risk.risk_level.toUpperCase()}
                                          size="small"
                                          sx={{ 
                                            height: '20px',
                                            fontSize: '0.65rem',
                                            bgcolor: getRiskColor(risk.risk_level),
                                            color: 'white',
                                            fontWeight: 'bold'
                                          }}
                                        />
                                        <Chip 
                                          label={risk.risk_category}
                                          size="small"
                                          variant="outlined"
                                          sx={{ height: '20px', fontSize: '0.65rem' }}
                                        />
                                        {risk.risk_score > 0 && (
                                          <Typography variant="caption" color="text.secondary">
                                            Score: {risk.risk_score}
                                          </Typography>
                                        )}
                                      </>
                                    )}
                                  </Box>
                                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                                    <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                                      {diff.status || 'unknown'}
                                    </Typography>
                                    {hasContent && (
                                      <Chip 
                                        label="Content" 
                                        size="small" 
                                        color="info" 
                                        variant="outlined"
                                        sx={{ fontSize: '0.65rem', height: '18px' }}
                                      />
                                    )}
                                  </Box>
                                </Box>
                              </AccordionSummary>
                              <AccordionDetails sx={{ p: 0 }}>
                                {/* Risk Findings */}
                                {risk && risk.findings && risk.findings.length > 0 && (
                                  <Box sx={{ p: 1.5, bgcolor: '#fafafa', borderBottom: '1px solid #e0e0e0' }}>
                                    <Typography variant="caption" fontWeight="bold" sx={{ mb: 1, display: 'block' }}>
                                      Findings:
                                    </Typography>
                                    {risk.findings.map((finding, idx) => (
                                      <Alert 
                                        key={idx}
                                        severity={finding.severity === 'critical' ? 'error' : 
                                                 finding.severity === 'high' ? 'warning' : 'info'}
                                        sx={{ mb: 1 }}
                                        icon={getRiskIcon(finding.severity)}
                                      >
                                        <Typography variant="body2">{finding.message}</Typography>
                                      </Alert>
                                    ))}
                                  </Box>
                                )}
                                
                                {/* Side-by-side diff display */}
                                <Box sx={{ p: 1.5 }}>
                                  {renderComponentDiff(component, diff)}
                                </Box>
                              </AccordionDetails>
                            </Accordion>
                          )
                        })}
                      </Box>
                    </Box>
                  )}
                  
                  {/* No results message */}
                  {getFilteredComponents().length === 0 && (riskFilter !== 'all' || categoryFilter !== 'all') && (
                    <Box sx={{ p: 3, textAlign: 'center' }}>
                      <Typography variant="body2" color="text.secondary">
                        No components match the selected filters
                      </Typography>
                      <Button 
                        size="small" 
                        onClick={() => {
                          setRiskFilter('all')
                          setCategoryFilter('all')
                        }}
                        sx={{ mt: 1 }}
                      >
                        Clear Filters
                      </Button>
                    </Box>
                  )}
                </Box>
              )}
            </Box>
          )}
        </Box>
      )}

    </CustomerContainer>
  )
}

export default CompareFingerprintsScreen;

