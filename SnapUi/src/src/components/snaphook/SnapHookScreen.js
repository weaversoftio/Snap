import React, { useState, useEffect } from 'react';
import { useSelector } from 'react-redux';
import { Box, Typography, Paper, Button } from '@mui/material';
import SnapHookManagement from '../SnapHook/SnapHookManagement';
import SnapHookStatus from '../SnapHook/SnapHookStatus';


const SnapHookScreen = () => {
  const [statusView, setStatusView] = useState(false);
  const [selectedHookForStatus, setSelectedHookForStatus] = useState(null);
  
  const { selectedCluster } = useSelector(state => state.cluster);

  const handleHookSelect = (hookName) => {
    setSelectedHookForStatus({ name: hookName });
    setStatusView(true);
  };

  const handleCloseStatusView = () => {
    setStatusView(false);
    setSelectedHookForStatus(null);
  };

  if (!selectedCluster) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography variant="h4" gutterBottom>
          SnapHook
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Please select a cluster to manage SnapHook webhooks.
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ width: '100%' }}>
      {statusView ? (
        <Box sx={{ mb: 3 }}>
          <Button
            variant="outlined"
            onClick={handleCloseStatusView}
            sx={{ mb: 2 }}
          >
            ← Back to SnapHooks
          </Button>
          {selectedHookForStatus && (
            <SnapHookStatus hookName={selectedHookForStatus.name} />
          )}
        </Box>
      ) : (
        <SnapHookManagement 
          clusterName={selectedCluster.name}
          clusterConfig={selectedCluster}
          onHookSelect={handleHookSelect}
        />
      )}
    </Box>
  );
};

export default SnapHookScreen;
