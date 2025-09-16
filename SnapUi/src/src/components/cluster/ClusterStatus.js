import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Alert,
  AlertTitle
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  ExpandMore as ExpandMoreIcon,
  Computer as ComputerIcon,
  Schedule as ScheduleIcon
} from '@mui/icons-material';
import { clusterStatusApi } from '../../api/clusterStatusApi';
import { useSnackbar } from 'notistack';
import { useSelector } from 'react-redux';

const ClusterStatus = () => {
  const [clusterStatus, setClusterStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { enqueueSnackbar } = useSnackbar();
  
  // Get selected cluster from Redux state
  const { selectedCluster } = useSelector(state => state.cluster);

  const fetchClusterStatus = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Pass the selected cluster name to the API
      const clusterName = selectedCluster?.name || null;
      const response = await clusterStatusApi.getClusterStatus(clusterName);
      
      if (response.success) {
        setClusterStatus(response.cluster_status);
      } else {
        setError(response.message);
      }
    } catch (err) {
      setError('Failed to fetch cluster status');
      enqueueSnackbar('Failed to fetch cluster status', { variant: 'error' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Only fetch if we have a selected cluster
    if (selectedCluster?.name) {
      fetchClusterStatus();
      
      // Refresh every 30 seconds
      const interval = setInterval(fetchClusterStatus, 30000);
      return () => clearInterval(interval);
    } else {
      // Clear status when no cluster is selected
      setClusterStatus(null);
      setLoading(false);
      setError(null);
    }
  }, [selectedCluster?.name]);

  const getStatusColor = (status) => {
    switch (status) {
      case 'ready':
        return 'success';
      case 'not_ready':
        return 'warning';
      default:
        return 'default';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'ready':
        return <CheckCircleIcon color="success" />;
      case 'not_ready':
        return <WarningIcon color="warning" />;
      default:
        return <ErrorIcon color="error" />;
    }
  };

  const getCheckIcon = (checkStatus) => {
    return checkStatus === 'pass' ? 
      <CheckCircleIcon color="success" fontSize="small" /> : 
      <ErrorIcon color="error" fontSize="small" />;
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'Never';
    return new Date(timestamp).toLocaleString();
  };

  const getNodeStatusColor = (node) => {
    if (node.ready) return 'success';
    if (!node.is_recent) return 'error';
    return 'warning';
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', p: 4 }}>
        <CircularProgress />
        <Typography variant="body1" sx={{ ml: 2 }}>
          {selectedCluster?.name 
            ? `Loading cluster status for "${selectedCluster.name}"...`
            : 'Loading cluster status...'
          }
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error">
        <AlertTitle>Error</AlertTitle>
        {error}
      </Alert>
    );
  }

  if (!clusterStatus) {
    return (
      <Alert severity="info">
        <AlertTitle>No Data</AlertTitle>
        {selectedCluster?.name 
          ? `No cluster status data available for cluster "${selectedCluster.name}". Deploy the cluster monitor DaemonSet to start monitoring.`
          : 'No cluster selected. Please select a cluster to view its status.'
        }
      </Alert>
    );
  }

  return (
    <Box>
      {/* Overall Status */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            {getStatusIcon(clusterStatus.overall_status)}
            <Typography variant="h6" sx={{ ml: 1, fontWeight: 'bold' }}>
              Cluster Status
            </Typography>
            <Chip
              label={clusterStatus.overall_status === 'ready' ? 'Ready' : 'Not Ready'}
              color={getStatusColor(clusterStatus.overall_status)}
              sx={{ ml: 'auto' }}
            />
          </Box>
          
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {clusterStatus.ready_nodes} of {clusterStatus.total_nodes} nodes are ready
          </Typography>

          <Box sx={{ display: 'flex', gap: 2 }}>
            <Chip
              icon={<CheckCircleIcon />}
              label={`${clusterStatus.ready_nodes} Ready`}
              color="success"
              variant="outlined"
            />
            <Chip
              icon={<WarningIcon />}
              label={`${clusterStatus.not_ready_nodes} Not Ready`}
              color="warning"
              variant="outlined"
            />
          </Box>
        </CardContent>
      </Card>

      {/* Node Details */}
      {clusterStatus.node_details && clusterStatus.node_details.length > 0 && (
        <Card>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
              Node Details
            </Typography>
            
            {clusterStatus.node_details.map((node, index) => (
              <Accordion key={node.node_name} sx={{ mb: 1 }}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
                    <ComputerIcon sx={{ mr: 1 }} />
                    <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>
                      {node.node_name}
                    </Typography>
                    <Chip
                      label={node.ready ? 'Ready' : 'Not Ready'}
                      color={getNodeStatusColor(node)}
                      size="small"
                      sx={{ ml: 'auto', mr: 2 }}
                    />
                  </Box>
                </AccordionSummary>
                <AccordionDetails>
                  <Box sx={{ width: '100%' }}>
                    {/* Last Update */}
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                      <ScheduleIcon sx={{ mr: 1, fontSize: 16 }} />
                      <Typography variant="body2" color="text.secondary">
                        Last Update: {formatTimestamp(node.last_update)}
                      </Typography>
                      {!node.is_recent && (
                        <Chip
                          label="Stale"
                          color="error"
                          size="small"
                          sx={{ ml: 1 }}
                        />
                      )}
                    </Box>

                    {/* Check Results */}
                    {node.checks && (
                      <List dense>
                        {Object.entries(node.checks).map(([checkName, checkData]) => (
                          <React.Fragment key={checkName}>
                            <ListItem>
                              <ListItemIcon>
                                {getCheckIcon(checkData.status)}
                              </ListItemIcon>
                              <ListItemText
                                primary={
                                  <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                                    {checkName.toUpperCase()}
                                  </Typography>
                                }
                                secondary={
                                  <Box>
                                    <Typography variant="body2" color="text.secondary">
                                      Status: {checkData.status}
                                    </Typography>
                                    {checkData.details && (
                                      <Typography variant="caption" color="text.secondary">
                                        Details: {checkData.details}
                                      </Typography>
                                    )}
                                  </Box>
                                }
                              />
                            </ListItem>
                            {index < Object.keys(node.checks).length - 1 && <Divider />}
                          </React.Fragment>
                        ))}
                      </List>
                    )}

                    {/* Error Message */}
                    {node.error && (
                      <Alert severity="error" sx={{ mt: 1 }}>
                        {node.error}
                      </Alert>
                    )}
                  </Box>
                </AccordionDetails>
              </Accordion>
            ))}
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default ClusterStatus;
