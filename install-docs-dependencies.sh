#!/bin/bash

# Install documentation dependencies for SnapUI
echo "Installing documentation dependencies for SnapUI..."

cd SnapUi/src

# Install markdown rendering dependencies
npm install react-markdown@^9.0.1 remark-gfm@^4.0.0

echo "Dependencies installed successfully!"
echo ""
echo "To test the documentation:"
echo "1. Start the SnapUI development server: npm start"
echo "2. Navigate to http://localhost:3000"
echo "3. Login and click on 'Documentation' in the sidebar"
echo ""
echo "The documentation is now available offline within SnapUI!"

