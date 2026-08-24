export function handleApiError(error, defaultMessage = "An error occurred") {
  if (error.response?.status === 401) {
    return "Session expired. Please log in again.";
  }
  if (error.response?.status === 403) {
    return "You don't have permission to perform this action.";
  }
  if (error.response?.status === 404) {
    return "The requested resource was not found.";
  }
  if (error.response?.status === 400) {
    return error.response?.data?.detail || "Invalid request. Please check your data.";
  }
  if (error.response?.status >= 500) {
    return "Server error. Please try again later.";
  }
  if (error.response?.data?.detail) {
    return error.response.data.detail;
  }
  if (error.message) {
    if (error.message.includes("Unexpected token")) {
      return "Server returned an invalid response. Please try again.";
    }
    return error.message;
  }
  return defaultMessage;
}
