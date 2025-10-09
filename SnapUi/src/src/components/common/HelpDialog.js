import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  ListItemIcon,
  Divider,
  TextField,
  InputAdornment,
  CircularProgress,
  Alert,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Chip,
  IconButton,
  Tooltip
} from '@mui/material';
import {
  Help as HelpIcon,
  Search as SearchIcon,
  ExpandMore as ExpandMoreIcon,
  Close as CloseIcon,
  Description as DocIcon,
  Folder as FolderIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';
import { useSnackbar } from 'notistack';

const HelpDialog = ({ open, onClose }) => {
  const { enqueueSnackbar } = useSnackbar();
  const [navigation, setNavigation] = useState([]);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [docContent, setDocContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [expandedCategories, setExpandedCategories] = useState({});
  const [docTitle, setDocTitle] = useState('');
  const [docDescription, setDocDescription] = useState('');

  useEffect(() => {
    if (open) {
      loadNavigation();
    }
  }, [open]);

  const loadNavigation = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${window.ENV.apiUrl}/docs/navigation`);
      const data = await response.json();
      
      if (data.success) {
        setNavigation(data.navigation);
        setDocTitle(data.title);
        setDocDescription(data.description);
        
        // Expand first category by default
        if (data.navigation.length > 0 && data.navigation[0].type === 'category') {
          setExpandedCategories({ [data.navigation[0].title]: true });
        }
      } else {
        enqueueSnackbar('Failed to load documentation navigation', { variant: 'error' });
      }
    } catch (error) {
      enqueueSnackbar('Error loading documentation', { variant: 'error' });
      console.error('Error loading navigation:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadDocContent = async (filename) => {
    try {
      setLoading(true);
      const response = await fetch(`${window.ENV.apiUrl}/docs/content/${filename}`);
      const data = await response.json();
      
      if (data.success) {
        setDocContent(data.content);
        setSelectedDoc(filename);
      } else {
        enqueueSnackbar('Failed to load documentation content', { variant: 'error' });
      }
    } catch (error) {
      enqueueSnackbar('Error loading documentation content', { variant: 'error' });
      console.error('Error loading doc content:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }

    try {
      setSearching(true);
      const response = await fetch(`${window.ENV.apiUrl}/docs/search?query=${encodeURIComponent(searchQuery)}`);
      const data = await response.json();
      
      if (data.success) {
        setSearchResults(data.results);
      } else {
        enqueueSnackbar('Search failed', { variant: 'error' });
      }
    } catch (error) {
      enqueueSnackbar('Error searching documentation', { variant: 'error' });
      console.error('Error searching:', error);
    } finally {
      setSearching(false);
    }
  };

  const handleCategoryToggle = (categoryTitle) => {
    setExpandedCategories(prev => ({
      ...prev,
      [categoryTitle]: !prev[categoryTitle]
    }));
  };

  const handleDocSelect = (filename) => {
    loadDocContent(filename);
  };

  const handleClose = () => {
    setSelectedDoc(null);
    setDocContent('');
    setSearchQuery('');
    setSearchResults([]);
    onClose();
  };

  const renderDocContent = () => {
    if (!docContent) return null;

    return (
      <Box sx={{ mt: 2 }}>
        <Typography variant="h6" gutterBottom>
          {selectedDoc?.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase())}
        </Typography>
        <Divider sx={{ mb: 2 }} />
        <Box 
          sx={{ 
            '& h1, & h2, & h3, & h4, & h5, & h6': { 
              mt: 2, 
              mb: 1,
              color: 'primary.main'
            },
            '& p': { mb: 1 },
            '& ul, & ol': { pl: 2 },
            '& li': { mb: 0.5 },
            '& code': { 
              backgroundColor: 'grey.100', 
              px: 0.5, 
              py: 0.25, 
              borderRadius: 0.5,
              fontFamily: 'monospace'
            },
            '& pre': { 
              backgroundColor: 'grey.100', 
              p: 1, 
              borderRadius: 1,
              overflow: 'auto'
            },
            '& table': { 
              borderCollapse: 'collapse',
              width: '100%'
            },
            '& th, & td': { 
              border: '1px solid',
              borderColor: 'divider',
              p: 1
            },
            '& th': { 
              backgroundColor: 'grey.100',
              fontWeight: 'bold'
            }
          }}
          dangerouslySetInnerHTML={{ __html: docContent }}
        />
      </Box>
    );
  };

  const renderNavigation = () => {
    if (loading) {
      return (
        <Box display="flex" justifyContent="center" p={3}>
          <CircularProgress />
        </Box>
      );
    }

    return (
      <List>
        {navigation.map((item, index) => {
          if (item.type === 'category') {
            return (
              <Accordion 
                key={item.title}
                expanded={expandedCategories[item.title] || false}
                onChange={() => handleCategoryToggle(item.title)}
              >
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Box display="flex" alignItems="center">
                    <FolderIcon sx={{ mr: 1, color: 'primary.main' }} />
                    <Typography variant="subtitle1" fontWeight="bold">
                      {item.title}
                    </Typography>
                  </Box>
                </AccordionSummary>
                <AccordionDetails sx={{ p: 0 }}>
                  <List sx={{ pl: 2 }}>
                    {item.children.map((child, childIndex) => (
                      <ListItem key={childIndex} disablePadding>
                        <ListItemButton 
                          onClick={() => handleDocSelect(child.filename)}
                          selected={selectedDoc === child.filename}
                        >
                          <ListItemIcon>
                            <DocIcon />
                          </ListItemIcon>
                          <ListItemText primary={child.title} />
                        </ListItemButton>
                      </ListItem>
                    ))}
                  </List>
                </AccordionDetails>
              </Accordion>
            );
          } else {
            return (
              <ListItem key={index} disablePadding>
                <ListItemButton 
                  onClick={() => handleDocSelect(item.filename)}
                  selected={selectedDoc === item.filename}
                >
                  <ListItemIcon>
                    <DocIcon />
                  </ListItemIcon>
                  <ListItemText primary={item.title} />
                </ListItemButton>
              </ListItem>
            );
          }
        })}
      </List>
    );
  };

  const renderSearchResults = () => {
    if (!searchQuery) return null;

    return (
      <Box sx={{ mt: 2 }}>
        <Typography variant="h6" gutterBottom>
          Search Results for "{searchQuery}"
        </Typography>
        <Divider sx={{ mb: 2 }} />
        {searching ? (
          <Box display="flex" justifyContent="center" p={2}>
            <CircularProgress size={24} />
          </Box>
        ) : searchResults.length > 0 ? (
          <List>
            {searchResults.map((result, index) => (
              <ListItem key={index} disablePadding>
                <ListItemButton onClick={() => handleDocSelect(result.filename)}>
                  <ListItemIcon>
                    <DocIcon />
                  </ListItemIcon>
                  <ListItemText 
                    primary={result.title}
                    secondary={result.snippet}
                  />
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        ) : (
          <Alert severity="info">
            No results found for "{searchQuery}"
          </Alert>
        )}
      </Box>
    );
  };

  return (
    <Dialog 
      open={open} 
      onClose={handleClose}
      maxWidth="lg"
      fullWidth
      PaperProps={{
        sx: { height: '80vh' }
      }}
    >
      <DialogTitle>
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Box display="flex" alignItems="center">
            <HelpIcon sx={{ mr: 1, color: 'primary.main' }} />
            <Box>
              <Typography variant="h6">{docTitle}</Typography>
              <Typography variant="body2" color="text.secondary">
                {docDescription}
              </Typography>
            </Box>
          </Box>
          <Box display="flex" alignItems="center" gap={1}>
            <Tooltip title="Refresh">
              <IconButton onClick={loadNavigation} size="small">
                <RefreshIcon />
              </IconButton>
            </Tooltip>
            <IconButton onClick={handleClose} size="small">
              <CloseIcon />
            </IconButton>
          </Box>
        </Box>
      </DialogTitle>

      <DialogContent dividers>
        <Box display="flex" gap={2} height="100%">
          {/* Left Panel - Navigation */}
          <Box sx={{ width: '300px', borderRight: 1, borderColor: 'divider', pr: 2 }}>
            <TextField
              fullWidth
              placeholder="Search documentation..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon />
                  </InputAdornment>
                ),
              }}
              size="small"
              sx={{ mb: 2 }}
            />
            
            {renderSearchResults()}
            {!searchQuery && renderNavigation()}
          </Box>

          {/* Right Panel - Content */}
          <Box sx={{ flex: 1, pl: 2 }}>
            {loading ? (
              <Box display="flex" justifyContent="center" alignItems="center" height="100%">
                <CircularProgress />
              </Box>
            ) : selectedDoc ? (
              renderDocContent()
            ) : (
              <Box display="flex" flexDirection="column" alignItems="center" justifyContent="center" height="100%">
                <HelpIcon sx={{ fontSize: 64, color: 'grey.400', mb: 2 }} />
                <Typography variant="h6" color="text.secondary" gutterBottom>
                  Welcome to SNAP Documentation
                </Typography>
                <Typography variant="body2" color="text.secondary" textAlign="center">
                  Select a document from the navigation panel to view its content,<br />
                  or use the search function to find specific information.
                </Typography>
              </Box>
            )}
          </Box>
        </Box>
      </DialogContent>

      <DialogActions>
        <Button onClick={handleClose}>
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default HelpDialog;
