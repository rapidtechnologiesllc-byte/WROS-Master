import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  Container,
  Table,
  Button,
  Modal,
  Form,
  Alert,
  Badge,
  Row,
  Col
} from 'react-bootstrap';
import { Plus, Edit, Trash2, GripVertical } from 'lucide-react';
import { toast } from 'react-toastify';

/**
 * AdminAgentConfig - Agent Configuration Management Screen
 *
 * Allows admins to:
 * - View all configured agents in pipeline order
 * - Create new agents with queue settings
 * - Edit existing agent configurations
 * - Delete agents (with confirmation)
 * - Drag-to-reorder agents by pipeline sequence
 *
 * Auto-syncs permissions when agents are created/updated.
 */

const AdminAgentConfig = () => {
  const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8080';

  // State
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [editingAgent, setEditingAgent] = useState(null);
  const [syncing, setSyncing] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    display_name: '',
    description: '',
    queue_name: '',
    next_queue_name: '',
    order: null,
    enabled: true
  });

  // Fetch agents on mount
  useEffect(() => {
    fetchAgents();
  }, []);

  const fetchAgents = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('access_token');
      const response = await axios.get(
        `${API_BASE_URL}/admin/agents/config`,
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );
      setAgents(response.data);
      setError(null);
    } catch (err) {
      const errorMsg = err.response?.data?.detail || 'Failed to load agents';
      setError(errorMsg);
      toast.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleShowModal = (agent = null) => {
    if (agent) {
      setEditingAgent(agent);
      setFormData(agent);
    } else {
      setEditingAgent(null);
      setFormData({
        name: '',
        display_name: '',
        description: '',
        queue_name: '',
        next_queue_name: '',
        order: null,
        enabled: true
      });
    }
    setShowModal(true);
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setEditingAgent(null);
  };

  const handleFormChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleSaveAgent = async () => {
    try {
      setSyncing(true);
      const token = localStorage.getItem('access_token');
      const headers = { Authorization: `Bearer ${token}` };

      if (editingAgent) {
        // Update existing
        await axios.put(
          `${API_BASE_URL}/admin/agents/config/${editingAgent.id}`,
          formData,
          { headers }
        );
        toast.success('Agent updated successfully');
      } else {
        // Create new
        await axios.post(
          `${API_BASE_URL}/admin/agents/config`,
          formData,
          { headers }
        );
        toast.success('Agent created successfully (permissions auto-synced)');
      }

      handleCloseModal();
      fetchAgents();
    } catch (err) {
      const errorMsg = err.response?.data?.detail || 'Failed to save agent';
      toast.error(errorMsg);
    } finally {
      setSyncing(false);
    }
  };

  const handleDeleteAgent = async (agentId) => {
    if (!window.confirm('Are you sure you want to delete this agent?')) {
      return;
    }

    try {
      const token = localStorage.getItem('access_token');
      await axios.delete(
        `${API_BASE_URL}/admin/agents/config/${agentId}`,
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );
      toast.success('Agent deleted successfully');
      fetchAgents();
    } catch (err) {
      const errorMsg = err.response?.data?.detail || 'Failed to delete agent';
      toast.error(errorMsg);
    }
  };

  if (loading) {
    return (
      <Container className="mt-4">
        <div className="text-center">
          <p>Loading agents...</p>
        </div>
      </Container>
    );
  }

  return (
    <Container className="mt-4">
      {/* Header */}
      <Row className="mb-4">
        <Col>
          <h2>Agent Configuration</h2>
          <p className="text-muted">
            Manage the agent pipeline and orchestration settings
          </p>
        </Col>
        <Col md="auto">
          <Button
            variant="primary"
            onClick={() => handleShowModal()}
            className="d-flex align-items-center gap-2"
          >
            <Plus size={18} /> Add Agent
          </Button>
        </Col>
      </Row>

      {/* Error Alert */}
      {error && (
        <Alert variant="danger" onClose={() => setError(null)} dismissible>
          {error}
        </Alert>
      )}

      {/* Sync Status */}
      {syncing && (
        <Alert variant="info">
          Syncing permissions to role templates...
        </Alert>
      )}

      {/* Agents Table */}
      <div className="table-responsive">
        <Table hover striped bordered>
          <thead className="table-light">
            <tr>
              <th style={{ width: '60px' }}>Order</th>
              <th>Name</th>
              <th>Display Name</th>
              <th>Input Queue</th>
              <th>Output Queue</th>
              <th>Status</th>
              <th style={{ width: '120px' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {agents && agents.length > 0 ? (
              agents.map(agent => (
                <tr key={agent.id}>
                  <td className="text-center">
                    <strong>{agent.order}</strong>
                  </td>
                  <td><code>{agent.name}</code></td>
                  <td>{agent.display_name}</td>
                  <td><small>{agent.queue_name}</small></td>
                  <td>
                    {agent.next_queue_name ? (
                      <small>{agent.next_queue_name}</small>
                    ) : (
                      <em className="text-muted">Final</em>
                    )}
                  </td>
                  <td>
                    {agent.enabled ? (
                      <Badge bg="success">Enabled</Badge>
                    ) : (
                      <Badge bg="secondary">Disabled</Badge>
                    )}
                  </td>
                  <td>
                    <Button
                      variant="outline-primary"
                      size="sm"
                      onClick={() => handleShowModal(agent)}
                      className="me-2"
                      title="Edit agent"
                    >
                      <Edit size={16} />
                    </Button>
                    <Button
                      variant="outline-danger"
                      size="sm"
                      onClick={() => handleDeleteAgent(agent.id)}
                      title="Delete agent"
                    >
                      <Trash2 size={16} />
                    </Button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="7" className="text-center text-muted py-4">
                  No agents configured. Create one to get started.
                </td>
              </tr>
            )}
          </tbody>
        </Table>
      </div>

      {/* Create/Edit Modal */}
      <Modal show={showModal} onHide={handleCloseModal} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>
            {editingAgent ? 'Edit Agent' : 'Create New Agent'}
          </Modal.Title>
        </Modal.Header>

        <Modal.Body>
          <Form>
            <Row>
              <Col md="6">
                <Form.Group className="mb-3">
                  <Form.Label>Agent Name (Unique ID)*</Form.Label>
                  <Form.Control
                    type="text"
                    name="name"
                    value={formData.name}
                    onChange={handleFormChange}
                    placeholder="e.g., thunder, recruitment_screener"
                    disabled={!!editingAgent}
                  />
                  <Form.Text className="text-muted">
                    Cannot be changed after creation
                  </Form.Text>
                </Form.Group>
              </Col>
              <Col md="6">
                <Form.Group className="mb-3">
                  <Form.Label>Display Name*</Form.Label>
                  <Form.Control
                    type="text"
                    name="display_name"
                    value={formData.display_name}
                    onChange={handleFormChange}
                    placeholder="e.g., AI Recruiter"
                  />
                </Form.Group>
              </Col>
            </Row>

            <Form.Group className="mb-3">
              <Form.Label>Description</Form.Label>
              <Form.Control
                as="textarea"
                rows={2}
                name="description"
                value={formData.description}
                onChange={handleFormChange}
                placeholder="What does this agent do in the pipeline?"
              />
            </Form.Group>

            <Row>
              <Col md="6">
                <Form.Group className="mb-3">
                  <Form.Label>Input Queue Name*</Form.Label>
                  <Form.Control
                    type="text"
                    name="queue_name"
                    value={formData.queue_name}
                    onChange={handleFormChange}
                    placeholder="e.g., input_queue"
                  />
                  <Form.Text className="text-muted">
                    Messages consumed from this queue
                  </Form.Text>
                </Form.Group>
              </Col>
              <Col md="6">
                <Form.Group className="mb-3">
                  <Form.Label>Output Queue Name</Form.Label>
                  <Form.Control
                    type="text"
                    name="next_queue_name"
                    value={formData.next_queue_name}
                    onChange={handleFormChange}
                    placeholder="e.g., recruiter_queue (leave empty if final)"
                  />
                  <Form.Text className="text-muted">
                    Leave empty for final agent in pipeline
                  </Form.Text>
                </Form.Group>
              </Col>
            </Row>

            <Row>
              <Col md="6">
                <Form.Group className="mb-3">
                  <Form.Label>Pipeline Order</Form.Label>
                  <Form.Control
                    type="number"
                    name="order"
                    value={formData.order || ''}
                    onChange={handleFormChange}
                    placeholder="Auto-calculated if blank"
                  />
                  <Form.Text className="text-muted">
                    Position in pipeline execution sequence
                  </Form.Text>
                </Form.Group>
              </Col>
              <Col md="6">
                <Form.Group className="mb-3">
                  <Form.Check
                    type="checkbox"
                    id="enabled"
                    name="enabled"
                    label="Enabled in Pipeline"
                    checked={formData.enabled}
                    onChange={handleFormChange}
                  />
                </Form.Group>
              </Col>
            </Row>

            {!editingAgent && (
              <Alert variant="info" className="mt-3">
                <strong>Auto-Sync Permissions:</strong> When this agent is created,
                permissions will be automatically synced to SuperUser role templates
                to ensure proper access control.
              </Alert>
            )}
          </Form>
        </Modal.Body>

        <Modal.Footer>
          <Button variant="secondary" onClick={handleCloseModal}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={handleSaveAgent}
            disabled={syncing || !formData.name || !formData.display_name}
          >
            {syncing ? 'Saving...' : editingAgent ? 'Update Agent' : 'Create Agent'}
          </Button>
        </Modal.Footer>
      </Modal>
    </Container>
  );
};

export default AdminAgentConfig;
