const OfferConfirmationEmail = ({
  candidateName,
  jobTitle,
  orgShortName,
  jobId,
  employmentType = "",
  compensation = "",
  location = "",
  joiningDate = "",
  hrName = "",
  hrContact = "",
  hrEmail = "hrdesk@blitzenx.com",
}) => {
  return `
  <!DOCTYPE html>
  <html>
  <head>
    <meta charset="UTF-8" />
    <title>Offer Confirmation</title>
  </head>
  <body style="background-color:#f4f4f4;padding:20px 0;font-family:Arial,sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr>
        <td align="center">
          <table
            width="650"
            cellpadding="0"
            cellspacing="0"
            border="0"
            style="background:#ffffff;border:1px solid #dddddd;border-radius:6px;"
          >
            <tr>
              <td style="padding:20px 30px;border-bottom:1px solid #eeeeee;">
                <h2 style="margin:0;font-size:22px;color:#222222;">
                  Offer Confirmation
                </h2>

                <p style="margin:5px 0 0;color:#777777;font-size:14px;">
                  Created by Onboarding Team
                </p>
              </td>
            </tr>

            <tr>
              <td
                style="
                  padding:30px;
                  color:#333333;
                  font-size:15px;
                  line-height:1.7;
                "
              >
                <p style="margin-top:0;">
                  <strong>Subject :</strong>
                  BlitzenX - Employment Offer - ${candidateName} (${jobTitle})
                </p>

                <p>Hello ${candidateName},</p>

                <p>
                  Thank you for your continued interest in the
                  <strong>${jobTitle}</strong> position with
                  <strong>${orgShortName}</strong>. We are pleased to inform you
                  that the hiring manager has made a positive decision on your
                  candidacy, and we'd like to move forward with the compensation
                  discussion.
                </p>

                <p>
                  Please find below the key details for your review:
                </p>

                <table
                  width="100%"
                  cellpadding="0"
                  cellspacing="0"
                  border="0"
                  style="margin:20px 0;"
                >
                  <tr>
                    <td><strong>Role:</strong></td>
                    <td>${jobTitle}</td>
                  </tr>

                  <tr>
                    <td><strong>Job ID:</strong></td>
                    <td>${jobId}</td>
                  </tr>

                  <tr>
                    <td><strong>Employment Type:</strong></td>
                    <td>${employmentType}</td>
                  </tr>

                  <tr>
                    <td><strong>Compensation:</strong></td>
                    <td>${compensation}</td>
                  </tr>

                  <tr>
                    <td><strong>Location:</strong></td>
                    <td>${location}</td>
                  </tr>

                  <tr>
                    <td><strong>Tentative Joining Date:</strong></td>
                    <td>${joiningDate}</td>
                  </tr>
                </table>

                <p>
                  <strong>Upskilling Plan:</strong>
                  You will undergo a structured technology upskilling program in
                  <em>Guidewire</em> as part of your initial learning phase.
                </p>

                <h3 style="margin-top:30px;color:#222222;">
                  HRBP Contact Details
                </h3>

                <table width="100%">
                  <tr>
                    <td><strong>Name:</strong></td>
                    <td>${hrName}</td>
                  </tr>

                  <tr>
                    <td><strong>Contact:</strong></td>
                    <td>${hrContact}</td>
                  </tr>

                  <tr>
                    <td><strong>Email:</strong></td>
                    <td>
                      <a
                        href="mailto:${hrEmail}"
                        style="color:#1a73e8;text-decoration:none;"
                      >
                        ${hrEmail}
                      </a>
                    </td>
                  </tr>
                </table>

                <h3 style="margin-top:30px;color:#222222;">
                  Next Steps
                </h3>

                <ol style="padding-left:20px;">
                  <li>
                    Please confirm your acceptance of the proposed compensation
                    and joining date.
                  </li>

                  <li>
                    Once we receive your confirmation, we will initiate the
                    preparation of your formal offer letter and share onboarding
                    instructions.
                  </li>

                  <li>
                    Our HR team will also reach out to coordinate your
                    documentation and pre-joining formalities.
                  </li>
                </ol>

                <p>
                  Please review the above details and share your confirmation or
                  any questions you may have.
                </p>

                <p style="margin-top:30px;">
                  <strong>Thank you</strong>
                  <br />
                  BlitzenX - Onboarding Team
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
  </html>
  `;
};

export default OfferConfirmationEmail;
