import { Box, Button, Dialog, DialogTitle, DialogContent, DialogActions, Typography, Paper, CircularProgress, Chip } from "@mui/material"
import { useState, useEffect, useCallback } from "react"
import { useSnackbar } from 'notistack'
import { checkpointApi } from "../../api/checkpointApi"
import ReactJson from 'react-json-view'
import CloseIcon from '@mui/icons-material/Close'
import IconButton from '@mui/material/IconButton'

const ComponentDiffViewer = ({ open, onClose, componentName, podName1, checkpointName1, podName2, checkpointName2 }) => {
  const { enqueueSnackbar } = useSnackbar()
  const [loading, setLoading] = useState(false)
  const [diffData, setDiffData] = useState(null)

  const loadDiff = useCallback(async () => {
    if (!componentName || !podName1 || !checkpointName1 || !podName2 || !checkpointName2) {
      enqueueSnackbar("Missing required parameters", { variant: "error" })
      return
    }

    try {
      setLoading(true)
      const checkpoint1_clean = checkpointName1.replace(".tar", "")
      const checkpoint2_clean = checkpointName2.replace(".tar", "")
      
      const result = await checkpointApi.getComponentDiff(
        podName1,
        checkpoint1_clean,
        podName2,
        checkpoint2_clean,
        componentName
      )
      console.log('Component diff result:', {
        componentName,
        has_content_1: result.has_content_1,
        has_content_2: result.has_content_2,
        content_1_exists: result.content_1 !== null && result.content_1 !== undefined,
        content_2_exists: result.content_2 !== null && result.content_2 !== undefined,
        content_1_type: typeof result.content_1,
        content_2_type: typeof result.content_2,
        content_1_keys: result.content_1 && typeof result.content_1 === 'object' ? Object.keys(result.content_1) : null,
        content_2_keys: result.content_2 && typeof result.content_2 === 'object' ? Object.keys(result.content_2) : null
      })
      setDiffData(result)
    } catch (error) {
      console.error("Failed to load diff:", error)
      enqueueSnackbar(`Failed to load diff: ${error.message || 'Unknown error'}`, { variant: "error" })
    } finally {
      setLoading(false)
    }
  }, [componentName, podName1, checkpointName1, podName2, checkpointName2, enqueueSnackbar])

  // Load diff when dialog opens
  useEffect(() => {
    if (open && componentName) {
      loadDiff()
    } else {
      setDiffData(null)
    }
  }, [open, componentName, loadDiff])

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
    
    // Simple diff: compare line by line
    const maxLines = Math.max(lines1.length, lines2.length)
    const diff = []
    
    for (let i = 0; i < maxLines; i++) {
      const line1 = lines1[i]
      const line2 = lines2[i]
      
      if (line1 === undefined) {
        // Only in checkpoint 2 (added)
        diff.push({ type: 'added', left: null, right: line2, lineNum: i + 1 })
      } else if (line2 === undefined) {
        // Only in checkpoint 1 (removed)
        diff.push({ type: 'removed', left: line1, right: null, lineNum: i + 1 })
      } else if (line1 === line2) {
        // Same in both (unchanged)
        diff.push({ type: 'unchanged', left: line1, right: line2, lineNum: i + 1 })
      } else {
        // Different (modified)
        diff.push({ type: 'modified', left: line1, right: line2, lineNum: i + 1 })
      }
    }
    
    return diff
  }

  const renderSideBySideDiff = () => {
    // Check if content actually exists (even if has_content flags are wrong)
    const hasContent1 = diffData.has_content_1 || (diffData.content_1 !== null && diffData.content_1 !== undefined)
    const hasContent2 = diffData.has_content_2 || (diffData.content_2 !== null && diffData.content_2 !== undefined)
    
    if (!hasContent1 && !hasContent2) {
      return (
        <Box sx={{ p: 3, textAlign: 'center' }}>
          <Typography variant="body2" color="text.secondary">
            Component is missing in both checkpoints
          </Typography>
        </Box>
      )
    }

    if (!hasContent1) {
      return (
        <Box sx={{ p: 2 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Component is missing in checkpoint 1
          </Typography>
          <Paper sx={{ p: 2, bgcolor: '#f5f5f5', maxHeight: '400px', overflow: 'auto' }}>
            <Typography variant="caption" color="text.secondary" gutterBottom>
              Checkpoint 2:
            </Typography>
            {typeof diffData.content_2 === 'object' && diffData.content_2 !== null ? (
              <ReactJson
                src={diffData.content_2}
                theme="rjv-default"
                collapsed={1}
                displayDataTypes={false}
                displayObjectSize={true}
                enableClipboard={true}
                style={{ fontSize: '0.75rem' }}
              />
            ) : (
              <Box sx={{ fontFamily: 'monospace', fontSize: '0.75rem', whiteSpace: 'pre-wrap' }}>
                {diffData.canonical_2 || JSON.stringify(diffData.content_2, null, 2)}
              </Box>
            )}
          </Paper>
        </Box>
      )
    }

    if (!hasContent2) {
      return (
        <Box sx={{ p: 2 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Component is missing in checkpoint 2
          </Typography>
          <Paper sx={{ p: 2, bgcolor: '#f5f5f5', maxHeight: '400px', overflow: 'auto' }}>
            <Typography variant="caption" color="text.secondary" gutterBottom>
              Checkpoint 1:
            </Typography>
            {typeof diffData.content_1 === 'object' && diffData.content_1 !== null ? (
              <ReactJson
                src={diffData.content_1}
                theme="rjv-default"
                collapsed={1}
                displayDataTypes={false}
                displayObjectSize={true}
                enableClipboard={true}
                style={{ fontSize: '0.75rem' }}
              />
            ) : (
              <Box sx={{ fontFamily: 'monospace', fontSize: '0.75rem', whiteSpace: 'pre-wrap' }}>
                {diffData.canonical_1 || JSON.stringify(diffData.content_1, null, 2)}
              </Box>
            )}
          </Paper>
        </Box>
      )
    }

    const diffLines = computeSideBySideDiff(diffData.content_1, diffData.content_2)

    return (
      <Box sx={{ display: 'flex', border: '1px solid #e0e0e0', borderRadius: 1, overflow: 'hidden' }}>
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
            maxHeight: 'calc(90vh - 300px)', 
            overflow: 'auto',
            fontFamily: 'monospace',
            fontSize: '0.875rem'
          }}>
            {diffLines.map((diff, index) => {
              let bgColor = 'transparent'
              if (diff.type === 'removed') bgColor = '#ffebee'
              else if (diff.type === 'modified') bgColor = '#fff3e0'
              
              return (
                <Box
                  key={index}
                  sx={{
                    display: 'flex',
                    bgcolor: bgColor,
                    borderLeft: diff.type === 'removed' ? '3px solid #f44336' : 
                               diff.type === 'modified' ? '3px solid #ff9800' : 'none',
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
                    {diff.left !== null ? diff.lineNum : ''}
                  </Box>
                  <Box sx={{ 
                    flex: 1, 
                    px: 1, 
                    py: 0.5,
                    wordBreak: 'break-all',
                    whiteSpace: 'pre-wrap'
                  }}>
                    {diff.left !== null ? diff.left : <span style={{ color: '#999' }}>—</span>}
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
            maxHeight: 'calc(90vh - 300px)', 
            overflow: 'auto',
            fontFamily: 'monospace',
            fontSize: '0.875rem'
          }}>
            {diffLines.map((diff, index) => {
              let bgColor = 'transparent'
              if (diff.type === 'added') bgColor = '#e8f5e9'
              else if (diff.type === 'modified') bgColor = '#fff3e0'
              
              return (
                <Box
                  key={index}
                  sx={{
                    display: 'flex',
                    bgcolor: bgColor,
                    borderLeft: diff.type === 'added' ? '3px solid #4caf50' : 
                               diff.type === 'modified' ? '3px solid #ff9800' : 'none',
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
                    {diff.right !== null ? diff.lineNum : ''}
                  </Box>
                  <Box sx={{ 
                    flex: 1, 
                    px: 1, 
                    py: 0.5,
                    wordBreak: 'break-all',
                    whiteSpace: 'pre-wrap'
                  }}>
                    {diff.right !== null ? diff.right : <span style={{ color: '#999' }}>—</span>}
                  </Box>
                </Box>
              )
            })}
          </Box>
        </Box>
      </Box>
    )
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
      PaperProps={{
        sx: { height: '90vh' }
      }}
    >
      <DialogTitle>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">
            Component Diff: {componentName}
          </Typography>
          <IconButton onClick={onClose} size="small">
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>
      <DialogContent dividers>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '200px' }}>
            <CircularProgress />
          </Box>
        ) : diffData ? (
          <Box>
            {/* Summary */}
            <Paper sx={{ p: 2, mb: 2, bgcolor: '#f5f5f5' }}>
              <Typography variant="subtitle2" gutterBottom>
                Component: {diffData.component_name}
              </Typography>
              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                <Typography variant="body2" color="text.secondary">
                  Checkpoint 1: {(diffData.has_content_1 || (diffData.content_1 !== null && diffData.content_1 !== undefined)) ? '✓ Present' : '✗ Missing'}
                  {diffData.source === 'fingerprint_cache' && (diffData.has_content_1 || (diffData.content_1 !== null && diffData.content_1 !== undefined)) && (
                    <Chip label="From Cache" size="small" color="success" variant="outlined" sx={{ ml: 1, height: '20px', fontSize: '0.65rem' }} />
                  )}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Checkpoint 2: {(diffData.has_content_2 || (diffData.content_2 !== null && diffData.content_2 !== undefined)) ? '✓ Present' : '✗ Missing'}
                  {diffData.source === 'fingerprint_cache' && (diffData.has_content_2 || (diffData.content_2 !== null && diffData.content_2 !== undefined)) && (
                    <Chip label="From Cache" size="small" color="success" variant="outlined" sx={{ ml: 1, height: '20px', fontSize: '0.65rem' }} />
                  )}
                </Typography>
              </Box>
              {diffData.source === 'fingerprint_cache' && (
                <Typography variant="caption" color="success.main" sx={{ display: 'block', mt: 1 }}>
                  ✓ Content loaded from fingerprint cache (fast)
                </Typography>
              )}
            </Paper>

            {/* Side-by-Side Diff */}
            {(diffData.has_content_1 || (diffData.content_1 !== null && diffData.content_1 !== undefined)) || 
             (diffData.has_content_2 || (diffData.content_2 !== null && diffData.content_2 !== undefined)) ? (
              <Paper sx={{ overflow: 'hidden' }}>
                {renderSideBySideDiff()}
              </Paper>
            ) : (
              <Box sx={{ p: 3, textAlign: 'center' }}>
                <Typography variant="body2" color="text.secondary">
                  Component is missing in both checkpoints
                </Typography>
              </Box>
            )}

            {/* Legend */}
            {diffData.has_content_1 && diffData.has_content_2 && (
              <Box sx={{ mt: 2, p: 1.5, bgcolor: '#f5f5f5', borderRadius: 1 }}>
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
        ) : (
          <Box sx={{ p: 3, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              Click "Load Diff" to view the component differences
            </Typography>
            <Button variant="contained" onClick={loadDiff} sx={{ mt: 2 }}>
              Load Diff
            </Button>
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  )
}

export default ComponentDiffViewer

