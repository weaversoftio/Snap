import React, { useState } from 'react';
import {
  Box,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
  Paper,
  Divider,
  IconButton,
  useTheme,
  useMediaQuery,
  Chip,
  Breadcrumbs,
  Link
} from '@mui/material';
import {
  Menu as MenuIcon,
  Home as HomeIcon,
  ChevronLeft as ChevronLeftIcon,
  ChevronRight as ChevronRightIcon,
  Book as BookIcon,
  Security as SecurityIcon,
  Settings as SettingsIcon,
  Help as HelpIcon,
  Api as ApiIcon,
  Build as BuildIcon
} from '@mui/icons-material';
import { documentationData } from '../../data/documentationData';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const drawerWidth = 300;

const DocumentationScreen = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [mobileOpen, setMobileOpen] = useState(false);
  const [selectedSection, setSelectedSection] = useState('getting-started');
  const [selectedPage, setSelectedPage] = useState('quick-start');

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const handleSectionSelect = (sectionId) => {
    setSelectedSection(sectionId);
    // Select first page of the section
    const section = documentationData.sections.find(s => s.id === sectionId);
    if (section && section.pages.length > 0) {
      setSelectedPage(section.pages[0].id);
    }
  };

  const handlePageSelect = (pageId) => {
    setSelectedPage(pageId);
  };

  const getCurrentSection = () => {
    return documentationData.sections.find(s => s.id === selectedSection);
  };

  const getCurrentPage = () => {
    const section = getCurrentSection();
    if (!section) return null;
    return section.pages.find(p => p.id === selectedPage);
  };

  const getSectionIcon = (sectionId) => {
    const icons = {
      'getting-started': <HomeIcon />,
      'user-guides': <BookIcon />,
      'api-reference': <ApiIcon />,
      'security-operations': <SecurityIcon />,
      'additional-resources': <HelpIcon />
    };
    return icons[sectionId] || <BookIcon />;
  };

  const drawer = (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
        <Typography variant="h6" sx={{ fontWeight: 'bold', color: 'primary.main' }}>
          📚 SNAP Documentation
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Container State Management Platform
        </Typography>
      </Box>

      {/* Navigation */}
      <Box sx={{ flex: 1, overflow: 'auto' }}>
        {documentationData.sections.map((section) => (
          <Box key={section.id} sx={{ mb: 1 }}>
            <ListItemButton
              onClick={() => handleSectionSelect(section.id)}
              sx={{
                backgroundColor: selectedSection === section.id ? 'primary.light' : 'transparent',
                color: selectedSection === section.id ? 'primary.contrastText' : 'inherit',
                '&:hover': {
                  backgroundColor: selectedSection === section.id ? 'primary.main' : 'action.hover',
                },
                px: 2,
                py: 1
              }}
            >
              <ListItemIcon sx={{ color: 'inherit', minWidth: 40 }}>
                {getSectionIcon(section.id)}
              </ListItemIcon>
              <ListItemText
                primary={section.title}
                primaryTypographyProps={{
                  fontWeight: selectedSection === section.id ? 'bold' : 'normal'
                }}
              />
            </ListItemButton>

            {/* Section Pages */}
            {selectedSection === section.id && (
              <List sx={{ pl: 2, py: 0 }}>
                {section.pages.map((page) => (
                  <ListItem key={page.id} disablePadding>
                    <ListItemButton
                      onClick={() => handlePageSelect(page.id)}
                      sx={{
                        backgroundColor: selectedPage === page.id ? 'secondary.light' : 'transparent',
                        color: selectedPage === page.id ? 'secondary.contrastText' : 'inherit',
                        borderRadius: 1,
                        mx: 1,
                        mb: 0.5,
                        '&:hover': {
                          backgroundColor: selectedPage === page.id ? 'secondary.main' : 'action.hover',
                        },
                      }}
                    >
                      <ListItemText
                        primary={page.title}
                        primaryTypographyProps={{
                          fontSize: '0.9rem',
                          fontWeight: selectedPage === page.id ? 'bold' : 'normal'
                        }}
                      />
                    </ListItemButton>
                  </ListItem>
                ))}
              </List>
            )}
          </Box>
        ))}
      </Box>

      {/* Footer */}
      <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider' }}>
        <Typography variant="body2" color="text.secondary" align="center">
          Offline Documentation
        </Typography>
        <Typography variant="caption" color="text.secondary" align="center" display="block">
          Version 1.0.0
        </Typography>
      </Box>
    </Box>
  );

  const currentPage = getCurrentPage();

  return (
    <Box sx={{ display: 'flex', height: '100vh' }}>
      {/* Mobile drawer */}
      {isMobile && (
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{
            keepMounted: true, // Better open performance on mobile.
          }}
          sx={{
            display: { xs: 'block', md: 'none' },
            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
          }}
        >
          {drawer}
        </Drawer>
      )}

      {/* Desktop drawer */}
      <Drawer
        variant="permanent"
        sx={{
          display: { xs: 'none', md: 'block' },
          '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
        }}
        open
      >
        {drawer}
      </Drawer>

      {/* Main content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: { md: `calc(100% - ${drawerWidth}px)` },
          backgroundColor: '#fafafa',
          minHeight: '100vh'
        }}
      >
        {/* Mobile menu button */}
        <IconButton
          color="inherit"
          aria-label="open drawer"
          edge="start"
          onClick={handleDrawerToggle}
          sx={{ mr: 2, display: { md: 'none' }, mb: 2 }}
        >
          <MenuIcon />
        </IconButton>

        {/* Breadcrumbs */}
        <Breadcrumbs sx={{ mb: 3 }}>
          <Link
            color="inherit"
            href="#"
            onClick={() => handleSectionSelect('getting-started')}
            sx={{ display: 'flex', alignItems: 'center' }}
          >
            <HomeIcon sx={{ mr: 0.5 }} fontSize="inherit" />
            Documentation
          </Link>
          <Typography color="text.primary">
            {getCurrentSection()?.title}
          </Typography>
          <Typography color="text.primary">
            {currentPage?.title}
          </Typography>
        </Breadcrumbs>

        {/* Content */}
        <Paper
          elevation={1}
          sx={{
            p: 4,
            borderRadius: 2,
            backgroundColor: 'white',
            minHeight: 'calc(100vh - 200px)'
          }}
        >
          {currentPage ? (
            <Box>
              {/* Page Header */}
              <Box sx={{ mb: 4, pb: 2, borderBottom: 1, borderColor: 'divider' }}>
                <Typography variant="h4" component="h1" sx={{ fontWeight: 'bold', mb: 1 }}>
                  {currentPage.title}
                </Typography>
                <Chip
                  label="Offline Documentation"
                  size="small"
                  color="primary"
                  variant="outlined"
                />
              </Box>

              {/* Markdown Content */}
              <Box
                sx={{
                  '& h1, & h2, & h3, & h4, & h5, & h6': {
                    color: 'primary.main',
                    fontWeight: 'bold',
                    mt: 3,
                    mb: 2
                  },
                  '& h1': {
                    fontSize: '2rem',
                    borderBottom: 2,
                    borderColor: 'primary.main',
                    pb: 1
                  },
                  '& h2': {
                    fontSize: '1.5rem',
                    borderBottom: 1,
                    borderColor: 'divider',
                    pb: 0.5
                  },
                  '& h3': {
                    fontSize: '1.25rem'
                  },
                  '& p': {
                    mb: 2,
                    lineHeight: 1.6
                  },
                  '& ul, & ol': {
                    mb: 2,
                    pl: 3
                  },
                  '& li': {
                    mb: 0.5
                  },
                  '& code': {
                    backgroundColor: '#f5f5f5',
                    padding: '2px 4px',
                    borderRadius: 1,
                    fontFamily: 'monospace',
                    fontSize: '0.9em'
                  },
                  '& pre': {
                    backgroundColor: '#f5f5f5',
                    padding: 2,
                    borderRadius: 1,
                    overflow: 'auto',
                    mb: 2,
                    border: 1,
                    borderColor: 'divider'
                  },
                  '& pre code': {
                    backgroundColor: 'transparent',
                    padding: 0
                  },
                  '& blockquote': {
                    borderLeft: 4,
                    borderColor: 'primary.main',
                    pl: 2,
                    ml: 0,
                    fontStyle: 'italic',
                    backgroundColor: '#f9f9f9',
                    py: 1,
                    borderRadius: 1
                  },
                  '& table': {
                    width: '100%',
                    borderCollapse: 'collapse',
                    mb: 2
                  },
                  '& th, & td': {
                    border: 1,
                    borderColor: 'divider',
                    padding: 1,
                    textAlign: 'left'
                  },
                  '& th': {
                    backgroundColor: '#f5f5f5',
                    fontWeight: 'bold'
                  },
                  '& a': {
                    color: 'primary.main',
                    textDecoration: 'none',
                    '&:hover': {
                      textDecoration: 'underline'
                    }
                  }
                }}
              >
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {currentPage.content}
                </ReactMarkdown>
              </Box>
            </Box>
          ) : (
            <Box sx={{ textAlign: 'center', py: 8 }}>
              <Typography variant="h5" color="text.secondary">
                Select a documentation page from the sidebar
              </Typography>
            </Box>
          )}
        </Paper>
      </Box>
    </Box>
  );
};

export default DocumentationScreen;

