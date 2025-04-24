import { StyleSheet, Text, View, TouchableOpacity, TextInput, ScrollView, Platform } from 'react-native';
import React, { useState } from 'react';
import * as DocumentPicker from 'expo-document-picker';

export default function HomeScreen() {
  const [fileName, setFileName] = useState('No file chosen');
  const [outputText, setOutputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<DocumentPicker.DocumentPickerAsset | null>(null);

  // *** Replace with the actual URL of your Flask backend's /upload endpoint ***
  // Find your computer's local IP address and use that, e.g., http://192.168.1.100:5000/upload
  // For Android emulator on the same machine, http://10.0.2.2:5000/upload might work
  const FLASK_BACKEND_URL = 'http://10.0.2.2:5000/upload'; // <<< --- REPLACE THIS URL --- >>>

  const pickFile = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: [
            'text/plain',
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        ],
        copyToCacheDirectory: false,
      });

      if (!result.canceled) {
        const file = result.assets[0];
        setFileName(file.name);
        setSelectedFile(file);
        setOutputText(''); // Clear previous output on new file selection
        setIsLoading(false); // Ensure loading is off
        console.log('File selected:', file.name);
        console.log('File URI:', file.uri);
      } else {
        console.log('Document picking canceled');
      }
    } catch (error) {
      console.error('Error picking document:', error);
      alert('Error picking document.');
    }
  };

  // *** handleAction function now sends file to backend using fetch ***
  const handleAction = async (action: string) => {
    console.log(`Action button pressed: ${action}`);
    if (!selectedFile) {
        alert('Please choose a file first.');
        return;
    }

    setIsLoading(true); // Start loading
    setOutputText(`Processing "${selectedFile.name}" with action: ${action}...`); // Update status message

    const fileUri = selectedFile.uri;
    const fileNameToSend = selectedFile.name;
    const fileTypeToSend = selectedFile.mimeType || 'application/octet-stream'; // Use mimeType or default

    try {
        // Fetch the file content from the URI as a Blob
        // This is necessary to get the file data in a format suitable for sending in FormData
        const fileContentBlob = await fetch(fileUri).then(response => response.blob());

        // Create FormData to send file and action to the backend
        const formData = new FormData();
        // Append the file blob with its name and type
        formData.append('document', fileContentBlob, fileNameToSend);
        // Append the selected action (e.g., 'summarize', 'simplify')
        formData.append('action', action);

        console.log(`Attempting to send file "${fileNameToSend}" to backend action "${action}" at ${FLASK_BACKEND_URL}`);

        // Make the POST request to your Flask backend's /upload endpoint
        const response = await fetch(FLASK_BACKEND_URL, {
            method: 'POST',
            body: formData,
            // fetch automatically sets Content-Type: multipart/form-data for FormData
            // Headers might be needed if your Flask app requires CORS handling
            // headers: { 'Content-Type': 'multipart/form-data' } is added automatically by fetch for FormData
        });

        // Check if the HTTP response status is OK (status in the 200 range)
        if (!response.ok) {
             const errorBody = await response.text(); // Read the response body as text to get error details
             throw new Error(`HTTP error! Status: ${response.status}, Body: ${errorBody}`);
        }

        // Assuming your Flask backend responds with JSON
        const data = await response.json();

        // Check the 'success' field in the JSON response from Flask
        if (data.success) {
            // Display the processed text received from the backend
            setOutputText(data.extracted_text);
            console.log("Backend response success:", data.extracted_text);
        } else {
            // Handle a 'success: false' response from your Flask backend's logic
            setOutputText(`Error: ${data.error || 'Processing failed with no specific error message from backend.'}`);
             console.error("Backend response failed:", data.error);
        }

    } catch (error: any) { // Catch network errors, JSON parsing errors, or HTTP errors
        console.error('API call failed:', error);
        // Display a user-friendly error message
        setOutputText(`Error: Could not process file. Please check console for details. ${error.message || error}`);
        // Optionally show an alert for critical network/API errors
        alert(`Error processing file. Check console for details.`);
    } finally {
        setIsLoading(false); // Stop loading regardless of success or failure
    }
  };

  // Functions for post-processing buttons (placeholder for now)
  const handlePostProcessing = (action: string) => {
    console.log(`${action} button pressed`);
    // These actions typically operate on the content of the outputText state variable.
    // We should ensure there is valid output before allowing these actions.
    if (outputText === '' || outputText.startsWith('Error:') || outputText.startsWith('Processing:')) {
         alert('No valid processed content available to perform this action.');
         return; // Stop if there's no valid output
    }
    // TODO: Implement actual Read Aloud, Share, Save logic using phone's capabilities or backend
    alert(`${action} feature not yet implemented for the processed content.`); // Provide feedback
  };


  return (
    <ScrollView contentContainerStyle={styles.scrollViewContent} style={styles.container}>
      <Text style={styles.title}>ClarityAssist</Text>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Upload File</Text>
        <Text style={styles.cardDescription}>Upload a document to simplify.</Text>
        <View style={styles.fileInputArea}>
          <TouchableOpacity style={styles.customFileUpload} onPress={pickFile} disabled={isLoading}>
            <Text style={styles.buttonText}>Choose File</Text>
          </TouchableOpacity>
          <Text style={styles.fileName}>{fileName}</Text>
        </View>
      </View>

      <View style={styles.actionButtonsGrid}>
        {/* Buttons are disabled if no file is selected OR if processing is already ongoing */}
        <TouchableOpacity style={styles.actionButton} onPress={() => handleAction('summarize')} disabled={!selectedFile || isLoading}>
          <Text style={styles.buttonText}>Summarize</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.actionButton} onPress={() => handleAction('simplify')} disabled={!selectedFile || isLoading}>
          <Text style={styles.buttonText}>Simplify</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.actionButton} onPress={() => handleAction('extract-instructions')} disabled={!selectedFile || isLoading}>
          <Text style={styles.buttonText}>Extract Instructions</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.actionButton} onPress={() => handleAction('analyze')} disabled={!selectedFile || isLoading}>
          <Text style={styles.buttonText}>Analyze File</Text>
        </TouchableOpacity>
      </View>

      {isLoading && (
           <Text style={styles.loadingMessage}>Processing...</Text>
      )}

      {/* Show Results Section only if outputText is not a processing message and not empty */}
      {outputText !== '' && !outputText.startsWith('Processing:') && ( // Also hide if it's an error message
         <View style={[styles.card, styles.resultsSection]}>
           <Text style={styles.cardTitle}>Processed Content</Text>
           <ScrollView style={styles.outputTextView}>
              <Text style={styles.outputText}>{outputText}</Text>
           </ScrollView>
         </View>
      )}

      {/* Show Error Section if outputText is an error message */}
      {outputText.startsWith('Error:') && (
           <View style={[styles.card, styles.resultsSection, styles.errorSection]}>
               <Text style={styles.cardTitle}>Error</Text>
               <ScrollView style={styles.outputTextView}>
                   <Text style={styles.errorText}>{outputText}</Text> {/* Display error message */}
               </ScrollView>
           </View>
      )}


       {/* Show Post-processing Actions only if outputText is a valid processed content */}
       {outputText !== '' && !outputText.startsWith('Processing:') && !outputText.startsWith('Error:') && (
           <View style={styles.postProcessingActions}>
               {/* Buttons are disabled if processing is ongoing or no valid output */}
               <TouchableOpacity style={styles.postProcessingButton} onPress={() => handlePostProcessing('Read Aloud')} disabled={isLoading || outputText === '' || outputText.startsWith('Error:') || outputText.startsWith('Processing:')}>
                 <Text style={styles.postProcessingButtonText}>Read Aloud</Text>
               </TouchableOpacity>
               <TouchableOpacity style={styles.postProcessingButton} onPress={() => handlePostProcessing('Share')} disabled={isLoading || outputText === '' || outputText.startsWith('Error:') || outputText.startsWith('Processing:')}>
                 <Text style={styles.postProcessingButtonText}>Share</Text>
               </TouchableOpacity>
               <TouchableOpacity style={styles.postProcessingButton} onPress={() => handlePostProcessing('Save')} disabled={isLoading || outputText === '' || outputText.startsWith('Error:') || outputText.startsWith('Processing:')}>
                 <Text style={styles.postProcessingButtonText}>Save</Text>
               </TouchableOpacity>
           </View>
       )}


    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f4f4e0',
    padding: 20,
  },
  scrollViewContent: {
    flexGrow: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingBottom: 50,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#005f5f',
    marginBottom: 25,
    textAlign: 'center',
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 10,
    padding: 20,
    marginBottom: 25,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 5,
    width: '100%',
    maxWidth: 600,
    alignItems: 'center',
  },
  cardTitle: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#005f5f',
    marginBottom: 12,
    textAlign: 'center',
  },
  cardDescription: {
    fontSize: 16,
    color: '#333',
    marginBottom: 18,
    textAlign: 'center',
    paddingHorizontal: 10,
  },
  fileInputArea: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    flexWrap: 'wrap',
    gap: 15,
    marginTop: 10,
  },
  customFileUpload: {
    backgroundColor: '#008080',
    paddingVertical: 14,
    paddingHorizontal: 25,
    borderRadius: 6,
    minHeight: 48,
    justifyContent: 'center',
    alignItems: 'center',
  },
  buttonText: {
    color: 'white',
    fontSize: 17,
    fontWeight: 'bold',
    textAlign: 'center',
  },
  fileName: {
    fontSize: 16,
    fontStyle: 'italic',
    color: '#555',
    flexShrink: 1,
    maxWidth: '60%',
  },
  actionButtonsGrid: {
    flexDirection: 'column',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 15,
    marginBottom: 25,
    width: '100%',
    maxWidth: 600,
  },
  actionButton: {
    backgroundColor: '#008080',
    paddingVertical: 14,
    paddingHorizontal: 20,
    borderRadius: 6,
    minHeight: 48,
    justifyContent: 'center',
    alignItems: 'center',
    width: '80%',
    maxWidth: 300,
  },
   resultsSection: {
     alignItems: 'stretch',
   },
   errorSection: { // Added style for error messages
       backgroundColor: '#ffcccc', // Light red background for errors
       borderColor: '#cc0000', // Dark red border
       borderWidth: 1,
   },
  outputTextView: {
     backgroundColor: '#eee',
     borderRadius: 5,
     padding: 15,
     marginTop: 15,
     maxHeight: 300,
     minHeight: 100,
     width: '100%',
  },
  outputText: {
    fontSize: 16,
    color: '#333',
    lineHeight: 24,
  },
  errorText: { // Added style for error text color
       fontSize: 16,
       color: '#cc0000', // Dark red text color for errors
       lineHeight: 24,
  },
  postProcessingActions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: 15,
    marginTop: 10,
    width: '100%',
    maxWidth: 600,
  },
  postProcessingButton: {
     backgroundColor: '#d3d3d3',
     paddingVertical: 10,
     paddingHorizontal: 20,
     borderRadius: 5,
     minHeight: 44,
     justifyContent: 'center',
     alignItems: 'center',
     flex: 1,
     minWidth: 100,
  },
  postProcessingButtonText: {
      color: '#333',
      fontSize: 15,
      fontWeight: 'bold',
      textAlign: 'center',
  },
  loadingMessage: {
      fontSize: 18,
      color: '#008080',
      textAlign: 'center',
      marginTop: 10,
      marginBottom: 10,
  },
});