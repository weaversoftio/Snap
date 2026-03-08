import React, { createContext, useContext, useState, useEffect, useMemo } from 'react';
import { ThemeProvider as MuiThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';

const ThemeContext = createContext();

const DARK_MODE_KEY = 'darkMode';

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};

export const ThemeProvider = ({ children }) => {
  // Initialize dark mode from localStorage, default to false
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem(DARK_MODE_KEY);
    return saved ? JSON.parse(saved) : false;
  });

  // Persist dark mode preference to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem(DARK_MODE_KEY, JSON.stringify(darkMode));
  }, [darkMode]);

  // Toggle dark mode
  const toggleDarkMode = () => {
    setDarkMode((prev) => !prev);
  };

  // Create Material-UI theme based on dark mode preference
  const theme = useMemo(
    () =>
      createTheme({
        palette: {
          mode: darkMode ? 'dark' : 'light',
          primary: {
            main: darkMode ? '#1565c0' : '#1565c0',
            light: darkMode ? '#1e88e5' : '#1e88e5',
            dark: darkMode ? '#0d47a1' : '#0d47a1',
            contrastText: '#ffffff',
          },
          secondary: {
            main: darkMode ? '#1976d2' : '#1976d2',
            light: darkMode ? '#42a5f5' : '#42a5f5',
            dark: darkMode ? '#1565c0' : '#1565c0',
            contrastText: '#ffffff',
          },
          background: {
            default: darkMode ? '#0f172a' : '#f8fafc',
            paper: darkMode ? '#1e293b' : '#ffffff',
          },
          text: {
            primary: darkMode ? '#f1f5f9' : '#0f172a',
            secondary: darkMode ? '#cbd5e1' : '#475569',
          },
        },
        typography: {
          fontFamily: [
            '-apple-system',
            'BlinkMacSystemFont',
            '"Segoe UI"',
            'Roboto',
            '"Helvetica Neue"',
            'Arial',
            'sans-serif',
          ].join(','),
          h1: {
            fontWeight: 700,
            letterSpacing: '-0.02em',
          },
          h2: {
            fontWeight: 700,
            letterSpacing: '-0.01em',
          },
          h3: {
            fontWeight: 600,
            letterSpacing: '-0.01em',
          },
          h4: {
            fontWeight: 600,
          },
          h5: {
            fontWeight: 600,
          },
          h6: {
            fontWeight: 600,
          },
          button: {
            textTransform: 'none',
            fontWeight: 600,
            letterSpacing: '0.02em',
          },
        },
        shape: {
          borderRadius: 12,
        },
        shadows: [
          'none',
          '0px 1px 2px rgba(0, 0, 0, 0.05)',
          '0px 1px 3px rgba(0, 0, 0, 0.1), 0px 1px 2px rgba(0, 0, 0, 0.06)',
          '0px 4px 6px -1px rgba(0, 0, 0, 0.1), 0px 2px 4px -1px rgba(0, 0, 0, 0.06)',
          '0px 10px 15px -3px rgba(0, 0, 0, 0.1), 0px 4px 6px -2px rgba(0, 0, 0, 0.05)',
          '0px 20px 25px -5px rgba(0, 0, 0, 0.1), 0px 10px 10px -5px rgba(0, 0, 0, 0.04)',
          '0px 25px 50px -12px rgba(0, 0, 0, 0.25)',
          ...Array(18).fill('0px 25px 50px -12px rgba(0, 0, 0, 0.25)'),
        ],
        components: {
          MuiButton: {
            styleOverrides: {
              root: {
                borderRadius: 10,
                padding: '10px 24px',
                fontSize: '0.9375rem',
                fontWeight: 600,
                textTransform: 'none',
                boxShadow: 'none',
                transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                '&:hover': {
                  boxShadow: '0px 4px 12px rgba(21, 101, 192, 0.4)',
                  transform: 'translateY(-1px)',
                },
                '&:active': {
                  transform: 'translateY(0px)',
                },
              },
              contained: {
                background: darkMode 
                  ? 'linear-gradient(135deg, #1565c0 0%, #1e88e5 100%)'
                  : 'linear-gradient(135deg, #1565c0 0%, #1e88e5 100%)',
                color: '#ffffff',
                '&:hover': {
                  background: darkMode
                    ? 'linear-gradient(135deg, #1e88e5 0%, #42a5f5 100%)'
                    : 'linear-gradient(135deg, #1e88e5 0%, #42a5f5 100%)',
                  boxShadow: '0px 6px 20px rgba(21, 101, 192, 0.5)',
                },
                '&:disabled': {
                  background: darkMode ? '#334155' : '#e2e8f0',
                  color: darkMode ? '#64748b' : '#94a3b8',
                },
              },
              outlined: {
                borderWidth: '2px',
                borderColor: darkMode ? '#1565c0' : '#1565c0',
                color: darkMode ? '#1e88e5' : '#1565c0',
                '&:hover': {
                  borderWidth: '2px',
                  borderColor: darkMode ? '#1e88e5' : '#1e88e5',
                  backgroundColor: darkMode ? 'rgba(21, 101, 192, 0.1)' : 'rgba(21, 101, 192, 0.05)',
                  boxShadow: '0px 4px 12px rgba(21, 101, 192, 0.2)',
                },
              },
              text: {
                color: darkMode ? '#cbd5e1' : '#475569',
                '&:hover': {
                  backgroundColor: darkMode ? 'rgba(21, 101, 192, 0.1)' : 'rgba(21, 101, 192, 0.05)',
                },
              },
            },
          },
          MuiCard: {
            styleOverrides: {
              root: {
                borderRadius: 16,
                boxShadow: darkMode
                  ? '0px 4px 6px -1px rgba(0, 0, 0, 0.3), 0px 2px 4px -1px rgba(0, 0, 0, 0.2)'
                  : '0px 4px 6px -1px rgba(0, 0, 0, 0.1), 0px 2px 4px -1px rgba(0, 0, 0, 0.06)',
                transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                '&:hover': {
                  boxShadow: darkMode
                    ? '0px 10px 15px -3px rgba(0, 0, 0, 0.4), 0px 4px 6px -2px rgba(0, 0, 0, 0.3)'
                    : '0px 10px 15px -3px rgba(0, 0, 0, 0.1), 0px 4px 6px -2px rgba(0, 0, 0, 0.05)',
                },
              },
            },
          },
          MuiPaper: {
            styleOverrides: {
              root: {
                borderRadius: 16,
                backgroundImage: 'none',
              },
              elevation1: {
                boxShadow: darkMode
                  ? '0px 1px 3px rgba(0, 0, 0, 0.3)'
                  : '0px 1px 3px rgba(0, 0, 0, 0.1), 0px 1px 2px rgba(0, 0, 0, 0.06)',
              },
              elevation2: {
                boxShadow: darkMode
                  ? '0px 4px 6px -1px rgba(0, 0, 0, 0.3), 0px 2px 4px -1px rgba(0, 0, 0, 0.2)'
                  : '0px 4px 6px -1px rgba(0, 0, 0, 0.1), 0px 2px 4px -1px rgba(0, 0, 0, 0.06)',
              },
            },
          },
          MuiTextField: {
            styleOverrides: {
              root: {
                '& .MuiOutlinedInput-root': {
                  borderRadius: 10,
                  transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                  '&:hover .MuiOutlinedInput-notchedOutline': {
                    borderColor: darkMode ? '#1e88e5' : '#1565c0',
                    borderWidth: '2px',
                  },
                  '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                    borderColor: darkMode ? '#1e88e5' : '#1565c0',
                    borderWidth: '2px',
                  },
                },
              },
            },
          },
          MuiDialog: {
            styleOverrides: {
              paper: {
                borderRadius: 20,
                boxShadow: darkMode
                  ? '0px 25px 50px -12px rgba(0, 0, 0, 0.5)'
                  : '0px 25px 50px -12px rgba(0, 0, 0, 0.25)',
              },
            },
          },
          MuiAppBar: {
            styleOverrides: {
              root: {
                boxShadow: darkMode
                  ? '0px 2px 8px rgba(0, 0, 0, 0.3)'
                  : '0px 2px 8px rgba(0, 0, 0, 0.1)',
              },
            },
          },
          MuiListItemButton: {
            styleOverrides: {
              root: {
                borderRadius: 0,
                margin: '2px 8px',
                transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                '&:hover': {
                  backgroundColor: darkMode ? 'rgba(21, 101, 192, 0.15)' : 'rgba(21, 101, 192, 0.08)',
                },
                '&.Mui-selected': {
                  backgroundColor: darkMode ? '#1565c0' : '#1565c0',
                  color: '#ffffff',
                  '&:hover': {
                    backgroundColor: darkMode ? '#1e88e5' : '#1e88e5',
                  },
                },
              },
            },
          },
        },
      }),
    [darkMode]
  );

  const value = {
    darkMode,
    toggleDarkMode,
    theme,
  };

  return (
    <ThemeContext.Provider value={value}>
      <MuiThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </MuiThemeProvider>
    </ThemeContext.Provider>
  );
};

