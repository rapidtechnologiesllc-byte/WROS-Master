export const getRejectionEmailHTML = (candidateName = "Candidate") => `
  <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <p>Hello ${candidateName},</p>

    <p>
      Thank you for taking the time to meet with our team and for your
      interest in pursuing a career with BlitzenX. We appreciate the effort
      you put into the interview process and the opportunity to learn more
      about your experience and aspirations.
    </p>

    <p>
      After careful review, we believe that the requirements of the role and
      your current expertise do not align at this time. Accordingly, we would
      like to inform you that you are not in consideration for this position.
    </p>

    <p>
      We sincerely appreciate your interest in BlitzenX and encourage you to
      stay connected for future opportunities that better match your
      background.
    </p>

    <p>
      We wish you continued success in your professional journey.
    </p>

    <br />

    <p>Thanks,</p>
    <p>BlitzenX</p>
  </div>
`;
