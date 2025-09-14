import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Button,
  Paper,
  Grid2 as Grid,
  Card,
  CardContent,
  Chip,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Stack,
  CircularProgress,
  Alert
} from '@mui/material';
import {
  Add as AddIcon,
  PlayArrow as StartIcon,
  Stop as StopIcon,
  Delete as DeleteIcon,
  Visibility as WatchersIcon
} from '@mui/icons-material';
import { useSnackbar } from 'notistack';
import { CustomerContainer } from '../common/CustomContainer';
import { watcherApi } from '../../api/watcherApi';

const WatchersScreen = ({ selectedCluster }) => {
  const { enqueueSnackbar } = useSnackbar();
  const [watchers, setWatchers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [newWatcher, setNewWatcher] = useState({
    name: '',
    scope: 'cluster',
    trigger: 'startupProbe',
    namespace: ''
  });

  // Load watcher status for the selected cluster
  useEffect(() => {
    const loadWatcherStatus = async () => {
      if (selectedCluster) {
        setLoading(true);
        try {
          const status = await watcherApi.getWatcherStatus();
          // Convert API response to watcher format
          if (status.running) {
            setWatchers([{
              id: '1',
              name: `${selectedCluster.name} Watcher`,
              scope: 'cluster',
              trigger: 'startupProbe',
              status: 'running',
              created: new Date().toISOString()
            }]);
          } else {
            setWatchers([]);
          }
        } catch (error) {
          console.error('Error loading watcher status:', error);
          setWatchers([]);
        } finally {
          setLoading(false);
        }
      }
    };

    loadWatcherStatus();
  }, [selectedCluster]);

  const handleCreateWatcher = async () => {
    if (!newWatcher.name.trim()) {
      enqueueSnackbar('Watcher name is required', { variant: 'error' });
      return;
    }

    if (newWatcher.scope === 'namespace' && !newWatcher.namespace.trim()) {
      enqueueSnackbar('Namespace is required for namespace scope', { variant: 'error' });
      return;
    }

    try {
      // Create cluster config from selected cluster
      const clusterConfig = {
        cluster_config_details: {
          kube_api_url: selectedCluster.cluster_config_details.kube_api_url,
          token: selectedCluster.cluster_config_details.token
        },
        name: selectedCluster.name
      };

      // Start the watcher via API
      await watcherApi.startWatcher(selectedCluster.name, clusterConfig);
      
      // Refresh watcher status
      const status = await watcherApi.getWatcherStatus();
      if (status.running) {
        setWatchers([{
          id: '1',
          name: newWatcher.name,
          scope: newWatcher.scope,
          trigger: newWatcher.trigger,
          namespace: newWatcher.namespace || null,
          status: 'running',
          created: new Date().toISOString()
        }]);
      }

      setCreateDialogOpen(false);
      setNewWatcher({
        name: '',
        scope: 'cluster',
        trigger: 'startupProbe',
        namespace: ''
      });
      enqueueSnackbar('Watcher created and started successfully', { variant: 'success' });
    } catch (error) {
      console.error('Error creating watcher:', error);
      enqueueSnackbar('Failed to create watcher', { variant: 'error' });
    }
  };

  const handleStartWatcher = async (watcherId) => {
    try {
      const clusterConfig = {
        cluster_config_details: {
          kube_api_url: selectedCluster.cluster_config_details.kube_api_url,
          token: selectedCluster.cluster_config_details.token
        },
        name: selectedCluster.name
      };

      await watcherApi.startWatcher(selectedCluster.name, clusterConfig);
      
      setWatchers(prev => 
        prev.map(watcher => 
          watcher.id === watcherId 
            ? { ...watcher, status: 'running' }
            : watcher
        )
      );
      enqueueSnackbar('Watcher started', { variant: 'success' });
    } catch (error) {
      console.error('Error starting watcher:', error);
      enqueueSnackbar('Failed to start watcher', { variant: 'error' });
    }
  };

  const handleStopWatcher = async (watcherId) => {
    try {
      await watcherApi.stopWatcher();
      
      setWatchers(prev => 
        prev.map(watcher => 
          watcher.id === watcherId 
            ? { ...watcher, status: 'stopped' }
            : watcher
        )
      );
      enqueueSnackbar('Watcher stopped', { variant: 'success' });
    } catch (error) {
      console.error('Error stopping watcher:', error);
      enqueueSnackbar('Failed to stop watcher', { variant: 'error' });
    }
  };

  const handleDeleteWatcher = async (watcherId) => {
    try {
      // Stop the watcher first
      await watcherApi.stopWatcher();
      
      setWatchers(prev => prev.filter(watcher => watcher.id !== watcherId));
      enqueueSnackbar('Watcher deleted', { variant: 'success' });
    } catch (error) {
      console.error('Error deleting watcher:', error);
      enqueueSnackbar('Failed to delete watcher', { variant: 'error' });
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'running': return 'success';
      case 'stopped': return 'default';
      case 'error': return 'error';
      default: return 'default';
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (!selectedCluster) {
    return (
      <CustomerContainer title="Watchers" subtitle="Manage cluster watchers">
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
            Select a cluster to manage watchers
          </Typography>
        </Box>
      </CustomerContainer>
    );
  }

  return (
    <CustomerContainer title="Watchers" subtitle={`Manage watchers for ${selectedCluster.name}`}>
      <Stack spacing={3}>
        {/* Header with Create Button */}
        <Paper elevation={0} sx={{ p: 3, bgcolor: 'background.paper', borderRadius: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                Cluster Watchers
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Monitor and manage watchers for {selectedCluster.name}
              </Typography>
            </Box>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setCreateDialogOpen(true)}
              sx={{ textTransform: 'none' }}
            >
              Create Watcher
            </Button>
          </Box>
        </Paper>

        {/* Watchers List */}
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : watchers.length === 0 ? (
          <Paper elevation={0} sx={{ p: 4, textAlign: 'center', bgcolor: 'background.paper', borderRadius: 2 }}>
            <WatchersIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
            <Typography variant="h6" color="text.secondary" sx={{ mb: 1 }}>
              No Watchers Found
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Create your first watcher to start monitoring your cluster
            </Typography>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setCreateDialogOpen(true)}
              sx={{ textTransform: 'none' }}
            >
              Create Watcher
            </Button>
          </Paper>
        ) : (
          <Grid container spacing={2}>
            {watchers.map((watcher) => (
              <Grid item xs={12} md={6} lg={4} key={watcher.id}>
                <Card sx={{ height: '100%' }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                      <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                        {watcher.name}
                      </Typography>
                      <Chip
                        label={watcher.status}
                        color={getStatusColor(watcher.status)}
                        size="small"
                        sx={{ textTransform: 'capitalize' }}
                      />
                    </Box>
                    
                    <Stack spacing={1} sx={{ mb: 2 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" color="text.secondary">Scope:</Typography>
                        <Typography variant="body2" sx={{ textTransform: 'capitalize' }}>
                          {watcher.scope}
                        </Typography>
                      </Box>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" color="text.secondary">Trigger:</Typography>
                        <Typography variant="body2">
                          {watcher.trigger}
                        </Typography>
                      </Box>
                      {watcher.namespace && (
                        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                          <Typography variant="body2" color="text.secondary">Namespace:</Typography>
                          <Typography variant="body2">{watcher.namespace}</Typography>
                        </Box>
                      )}
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" color="text.secondary">Created:</Typography>
                        <Typography variant="body2">{formatDate(watcher.created)}</Typography>
                      </Box>
                    </Stack>

                    <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
                      {watcher.status === 'running' ? (
                        <Tooltip title="Stop Watcher">
                          <IconButton
                            size="small"
                            color="warning"
                            onClick={() => handleStopWatcher(watcher.id)}
                          >
                            <StopIcon />
                          </IconButton>
                        </Tooltip>
                      ) : (
                        <Tooltip title="Start Watcher">
                          <IconButton
                            size="small"
                            color="success"
                            onClick={() => handleStartWatcher(watcher.id)}
                          >
                            <StartIcon />
                          </IconButton>
                        </Tooltip>
                      )}
                      <Tooltip title="Delete Watcher">
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => handleDeleteWatcher(watcher.id)}
                        >
                          <DeleteIcon />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        )}
      </Stack>

      {/* Create Watcher Dialog */}
      <Dialog
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Create New Watcher</DialogTitle>
        <DialogContent>
          <Stack spacing={3} sx={{ mt: 1 }}>
            <TextField
              label="Watcher Name"
              value={newWatcher.name}
              onChange={(e) => setNewWatcher(prev => ({ ...prev, name: e.target.value }))}
              fullWidth
              required
            />
            
            <FormControl fullWidth>
              <InputLabel>Scope</InputLabel>
              <Select
                value={newWatcher.scope}
                onChange={(e) => setNewWatcher(prev => ({ ...prev, scope: e.target.value }))}
                label="Scope"
              >
                <MenuItem value="cluster">Cluster</MenuItem>
                <MenuItem value="namespace">Namespace</MenuItem>
              </Select>
            </FormControl>

            {newWatcher.scope === 'namespace' && (
              <TextField
                label="Namespace"
                value={newWatcher.namespace}
                onChange={(e) => setNewWatcher(prev => ({ ...prev, namespace: e.target.value }))}
                fullWidth
                required
                helperText="Enter the namespace to monitor"
              />
            )}

            <FormControl fullWidth>
              <InputLabel>Trigger</InputLabel>
              <Select
                value={newWatcher.trigger}
                onChange={(e) => setNewWatcher(prev => ({ ...prev, trigger: e.target.value }))}
                label="Trigger"
              >
                <MenuItem value="startupProbe">Startup Probe</MenuItem>
              </Select>
            </FormControl>

            <Alert severity="info">
              This watcher will monitor pods based on the selected scope and trigger conditions.
            </Alert>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateDialogOpen(false)}>
            Cancel
          </Button>
          <Button onClick={handleCreateWatcher} variant="contained">
            Create Watcher
          </Button>
        </DialogActions>
      </Dialog>
    </CustomerContainer>
  );
};

export default WatchersScreen;
