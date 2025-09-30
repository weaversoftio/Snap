// Example usage of the logs system
import { useLogs } from './components/common/LogsContext';

const ExampleComponent = () => {
  const { addLog, addErrorLog, addSuccessLog } = useLogs();

  const handleAction = () => {
    addLog('Starting action...');
    
    try {
      // Simulate some work
      addSuccessLog('Action completed successfully!');
    } catch (error) {
      addErrorLog('Action failed: ' + error.message);
    }
  };

  return (
    <button onClick={handleAction}>
      Test Logs
    </button>
  );
};
