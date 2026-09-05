/**
 * Progressive Document Upload Screen
 * ====================================
 * Multi-document upload with live status tracking
 * Uses SharePoint backend via DocumentService
 * Integrates with Celery async processing
 */

import React, { useState, useEffect } from 'react';
import styles from '../styles/DocumentUpload.module.css';
import { uploadResume } from '../services/api/documents';

export default function DocumentUploadScreen({ candidateId }) {
  // State management
  const [files, setFiles] = useState([]); // { id, file, name, size, progress, status, error }
  const [uploadInProgress, setUploadInProgress] = useState(false);
  const [completedCount, setCompletedCount] = useState(0);
  const [totalCount, setTotalCount] = useState(0);

  // Handle file selection
  const handleFileSelect = (event) => {
    const selectedFiles = Array.from(event.target.files);
    const newFiles = selectedFiles.map((file) => ({
      id: Math.random().toString(36).substr(2, 9),
      file,
      name: file.name,
      size: file.size,
      progress: 0,
      status: 'pending', // pending, uploading, completed, failed
      error: null,
      uploadedAt: null,
    }));

    setFiles([...files, ...newFiles]);
    setTotalCount((prev) => prev + selectedFiles.length);
  };

  // Upload single document
  const uploadDocument = async (fileObj) => {
    try {
      // Update UI: mark as uploading
      setFiles((prev) =>
        prev.map((f) =>
          f.id === fileObj.id
            ? { ...f, status: 'uploading', progress: 0 }
            : f
        )
      );

      // Call backend API
      const response = await uploadResume({
        candidateId,
        file: fileObj.file,
      });

      // Success
      setFiles((prev) =>
        prev.map((f) =>
          f.id === fileObj.id
            ? {
                ...f,
                status: 'completed',
                progress: 100,
                uploadedAt: new Date(),
                documentId: response.id,
              }
            : f
        )
      );

      setCompletedCount((prev) => prev + 1);

      return response;
    } catch (error) {
      // Error
      setFiles((prev) =>
        prev.map((f) =>
          f.id === fileObj.id
            ? {
                ...f,
                status: 'failed',
                error: error.message || 'Upload failed',
              }
            : f
        )
      );

      throw error;
    }
  };

  // Upload all documents
  const handleUploadAll = async () => {
    setUploadInProgress(true);

    const pendingFiles = files.filter((f) => f.status === 'pending');

    for (const fileObj of pendingFiles) {
      try {
        await uploadDocument(fileObj);
      } catch (err) {
        console.error(`Failed to upload ${fileObj.name}:`, err);
      }
    }

    setUploadInProgress(false);
  };

  // Calculate overall progress
  const overallProgress =
    files.length > 0 ? (completedCount / totalCount) * 100 : 0;
  const hasErrors = files.some((f) => f.status === 'failed');
  const allUploaded = files.length > 0 && completedCount === totalCount;

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        {/* Header */}
        <div className={styles.header}>
          <h1>Upload Documents</h1>
          <p>Upload one or more documents for processing</p>
        </div>

        {/* Upload Zone */}
        {!uploadInProgress && (
          <div className={styles.uploadZone}>
            <input
              type="file"
              multiple
              onChange={handleFileSelect}
              disabled={uploadInProgress}
              className={styles.fileInput}
              accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
            />
            <div className={styles.uploadPrompt}>
              <p className={styles.icon}>📄</p>
              <p className={styles.text}>
                Drag files here or click to browse
              </p>
              <p className={styles.subtext}>
                Supported: PDF, DOC, DOCX, JPG, PNG (Max 100MB each)
              </p>
            </div>
          </div>
        )}

        {/* Progress Bar */}
        {files.length > 0 && (
          <div className={styles.progressSection}>
            <div className={styles.progressInfo}>
              <span>
                {completedCount} of {totalCount} uploaded
              </span>
              <span className={styles.percentage}>
                {Math.round(overallProgress)}%
              </span>
            </div>
            <div className={styles.progressBar}>
              <div
                className={styles.progressFill}
                style={{ width: `${overallProgress}%` }}
              />
            </div>
          </div>
        )}

        {/* File List */}
        {files.length > 0 && (
          <div className={styles.fileList}>
            <table className={styles.fileTable}>
              <thead>
                <tr>
                  <th>Filename</th>
                  <th>Size</th>
                  <th>Status</th>
                  <th>Progress</th>
                </tr>
              </thead>
              <tbody>
                {files.map((file) => (
                  <tr key={file.id} className={styles[`status-${file.status}`]}>
                    <td className={styles.filename}>
                      <span className={styles.fileIcon}>
                        {getFileIcon(file.name)}
                      </span>
                      {file.name}
                    </td>
                    <td className={styles.size}>
                      {formatFileSize(file.size)}
                    </td>
                    <td className={styles.status}>
                      <span
                        className={`${styles.badge} ${
                          styles[`badge-${file.status}`]
                        }`}
                      >
                        {getStatusLabel(file.status)}
                      </span>
                      {file.error && (
                        <p className={styles.errorText}>{file.error}</p>
                      )}
                    </td>
                    <td className={styles.progress}>
                      {file.progress}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Status Messages */}
        {allUploaded && (
          <div className={styles.successMessage}>
            ✅ All documents uploaded successfully! Processing started.
          </div>
        )}

        {hasErrors && !allUploaded && (
          <div className={styles.errorMessage}>
            ⚠️ Some uploads failed. Retry or skip failed files.
          </div>
        )}

        {/* Action Buttons */}
        <div className={styles.actions}>
          {files.length > 0 && !uploadInProgress && !allUploaded && (
            <button
              className={styles.uploadButton}
              onClick={handleUploadAll}
              disabled={files.every((f) => f.status !== 'pending')}
            >
              Upload Documents
            </button>
          )}

          {allUploaded && (
            <button
              className={styles.doneButton}
              onClick={() => {
                // Return to candidate details or next step
                window.history.back();
              }}
            >
              Done
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// Helper functions
function getFileIcon(filename) {
  if (filename.endsWith('.pdf')) return '📕';
  if (filename.endsWith('.doc') || filename.endsWith('.docx')) return '📄';
  if (filename.match(/\.(jpg|jpeg|png|gif)$/i)) return '🖼️';
  return '📎';
}

function formatFileSize(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

function getStatusLabel(status) {
  const labels = {
    pending: 'Waiting',
    uploading: 'Uploading...',
    completed: 'Done',
    failed: 'Failed',
  };
  return labels[status] || status;
}
