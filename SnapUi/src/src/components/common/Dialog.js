import { DialogActions, DialogContent, DialogTitle, Dialog as MuiDialog } from "@mui/material"

const DialogComponent = ({
  children,
  title = '',
  open = false,
  onClose = () => null,
  renderButtons = null,
  paperProps={}
}) => (
  <MuiDialog
    open={open}
    onClose={onClose}
    PaperProps={{ 
      sx: { 
        paddingBlockEnd: '1rem',  
        flexGrow: 1, 
        maxWidth: 800, 
        borderRadius: '20px',
        ...paperProps 
      } 
    }}
    transitionDuration={{ enter: 300, exit: 200 }}
  >
    <DialogTitle 
      variant='h5'
      sx={{
        fontWeight: 600,
        padding: '24px 24px 16px 24px',
        borderBottom: '1px solid',
        borderColor: 'divider',
      }}
    >
      {title}
    </DialogTitle>
    <DialogContent sx={{ padding: '24px' }}>
      {children}
    </DialogContent>
    {renderButtons && (
      <DialogActions 
        sx={{
          marginRight: 18,
          padding: '16px 24px',
          borderTop: '1px solid',
          borderColor: 'divider',
          gap: 1,
        }}
      >
        {renderButtons()}
      </DialogActions>
    )}
  </MuiDialog>
)

export default DialogComponent;