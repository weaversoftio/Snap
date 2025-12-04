import { Box, Typography, Paper } from "@mui/material";
import { CustomerContainer } from "../common/CustomContainer";

const SettingsScreen = () => {
  return (
    <CustomerContainer title="Settings">
      <Paper elevation={0} sx={{ p: 3, bgcolor: 'background.paper', borderRadius: 2 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Settings
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Settings page coming soon...
        </Typography>
      </Paper>
    </CustomerContainer>
  );
};

export default SettingsScreen;

