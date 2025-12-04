import { Box, Typography, Paper, Switch, FormControlLabel } from "@mui/material";
import { CustomerContainer } from "../common/CustomContainer";
import { useTheme } from "../../contexts/ThemeContext";

const SettingsScreen = () => {
  const { darkMode, toggleDarkMode } = useTheme();

  return (
    <CustomerContainer title="Settings">
      <Paper 
        elevation={0} 
        sx={{ 
          p: 3, 
          bgcolor: 'background.paper',
          borderRadius: 2
        }}
      >
        {/* UI Section */}
        <Box>
          <Typography variant="h6" sx={{ mb: 2, fontSize: '1.1rem', fontWeight: 600 }}>
            UI
          </Typography>
          <FormControlLabel
            control={
              <Switch
                checked={darkMode}
                onChange={toggleDarkMode}
                color="primary"
              />
            }
            label="Dark Mode"
          />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1, ml: 4 }}>
            Enable dark mode to reduce eye strain in low-light conditions
          </Typography>
        </Box>
      </Paper>
    </CustomerContainer>
  );
};

export default SettingsScreen;

