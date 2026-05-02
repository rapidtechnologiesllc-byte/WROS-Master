export const getEmailBodyHTML = (candidateName) => {
  return `
    <p>Dear ${candidateName},</p>

    <p>We are pleased to inform you that your <b>pre-onboarding process</b> has been initiated.</p>

    <p>You are required to complete a few formalities by submitting documents on the HRMS portal.</p>

    <p><b>Next Steps:</b></p>
    <ul>
      <li>Log in to the HRMS portal</li>
      <li>Complete assigned tasks</li>
      <li>Upload required documents</li>
    </ul>

    <p>
      <b>Portal Link:</b> 
      <a href="https://your-hrms-link.com">Click here to access</a>
    </p>

    <p>If you have any questions, feel free to contact the HR team.</p>

    <p>Regards,<br/>HR Team</p>
  `;
};