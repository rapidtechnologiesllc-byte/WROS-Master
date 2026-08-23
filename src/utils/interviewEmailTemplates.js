export const getOnlineInterviewEmailTemplate = ({
  candidateName,
  jobTitle
}) => {
  return {
    subject: `Interview Invitation - ${jobTitle || "Interview"}`,
    body: `Dear ${candidateName || "Candidate"},

You have been scheduled for an online interview for ${jobTitle || "the role"}.

Please check your calendar invitation for the meeting details.

Best regards,
HR Team`
  };
};

export const getFaceToFaceInterviewEmailTemplate = ({
  candidateName,
  jobTitle
}) => {
  return {
    subject: `Face to Face Interview - ${jobTitle || "Interview"}`,
    body: `Dear ${candidateName || "Candidate"},

You have been scheduled for a face-to-face interview for ${jobTitle || "the role"}.

Please find the interview details below:

Location:
Date and Time:

Best regards,
HR Team`
  };
};