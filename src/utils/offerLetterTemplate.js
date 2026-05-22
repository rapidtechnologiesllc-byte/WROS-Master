import React from "react";

const OfferConfirmationEmail = ({
  candidateName,
  jobTitle,
  orgShortName,
  jobId,
  employmentType,
  compensation,
  location,
  joiningDate,
  hrName,
  hrContact,
  hrEmail = "hrdesk@blitzenx.com",
}) => {
  return (
    <div
      style={{
        backgroundColor: "#f4f4f4",
        padding: "20px 0",
        fontFamily: "Arial, sans-serif",
      }}
    >
      <table
        width="100%"
        cellPadding="0"
        cellSpacing="0"
        border="0"
      >
        <tbody>
          <tr>
            <td align="center">
              <table
                width="650"
                cellPadding="0"
                cellSpacing="0"
                border="0"
                style={{
                  backgroundColor: "#ffffff",
                  border: "1px solid #dddddd",
                  borderRadius: "6px",
                  overflow: "hidden",
                }}
              >
                {/* Header */}
                <tbody>
                  <tr>
                    <td
                      style={{
                        padding: "20px 30px",
                        borderBottom: "1px solid #eeeeee",
                      }}
                    >
                      <h2
                        style={{
                          margin: 0,
                          fontSize: "22px",
                          color: "#222222",
                        }}
                      >
                        Offer Confirmation
                      </h2>

                      <p
                        style={{
                          margin: "5px 0 0",
                          color: "#777777",
                          fontSize: "14px",
                        }}
                      >
                        Created by Onboarding Team
                      </p>
                    </td>
                  </tr>

                  {/* Body */}
                  <tr>
                    <td
                      style={{
                        padding: "30px",
                        color: "#333333",
                        fontSize: "15px",
                        lineHeight: "1.7",
                      }}
                    >
                      {/* Subject */}
                      <p style={{ marginTop: 0 }}>
                        <strong>Subject :</strong> BlitzenX - Employment Offer -
                        {" "}
                        {candidateName} ({jobTitle})
                      </p>

                      <p>Hello {candidateName},</p>

                      <p>
                        Thank you for your continued interest in the{" "}
                        <strong>{jobTitle}</strong> position with{" "}
                        <strong>{orgShortName}</strong>. I’m pleased to inform
                        you that the hiring manager has made a positive decision
                        on your candidacy, and we’d like to move forward with
                        the compensation discussion.
                      </p>

                      <p>
                        Please find below the key details for your review:
                      </p>

                      {/* Details Table */}
                      <table
                        width="100%"
                        cellPadding="0"
                        cellSpacing="0"
                        border="0"
                        style={{ margin: "20px 0" }}
                      >
                        <tbody>
                          <tr>
                            <td style={{ padding: "5px 0" }}>
                              <strong>Role:</strong>
                            </td>
                            <td style={{ padding: "5px 0" }}>
                              {jobTitle}
                            </td>
                          </tr>

                          <tr>
                            <td style={{ padding: "5px 0" }}>
                              <strong>Job ID:</strong>
                            </td>
                            <td style={{ padding: "5px 0" }}>
                              {jobId}
                            </td>
                          </tr>

                          <tr>
                            <td style={{ padding: "5px 0" }}>
                              <strong>Employment Type:</strong>
                            </td>
                            <td style={{ padding: "5px 0" }}>
                              {employmentType}
                            </td>
                          </tr>

                          <tr>
                            <td style={{ padding: "5px 0" }}>
                              <strong>Compensation:</strong>
                            </td>
                            <td style={{ padding: "5px 0" }}>
                              {compensation}
                            </td>
                          </tr>

                          <tr>
                            <td style={{ padding: "5px 0" }}>
                              <strong>Location:</strong>
                            </td>
                            <td style={{ padding: "5px 0" }}>
                              {location}
                            </td>
                          </tr>

                          <tr>
                            <td style={{ padding: "5px 0" }}>
                              <strong>Tentative Joining Date:</strong>
                            </td>
                            <td style={{ padding: "5px 0" }}>
                              {joiningDate}
                            </td>
                          </tr>
                        </tbody>
                      </table>

                      {/* Upskilling */}
                      <p>
                        <strong>Upskilling Plan:</strong> You will undergo a
                        structured technology upskilling program in{" "}
                        <em>Guidewire</em> as part of your initial learning
                        phase.
                      </p>

                      {/* HR Contact */}
                      <h3
                        style={{
                          marginTop: "30px",
                          color: "#222222",
                        }}
                      >
                        HRBP Contact Details
                      </h3>

                      <table
                        width="100%"
                        cellPadding="0"
                        cellSpacing="0"
                        border="0"
                      >
                        <tbody>
                          <tr>
                            <td style={{ padding: "4px 0" }}>
                              <strong>Name:</strong>
                            </td>
                            <td style={{ padding: "4px 0" }}>
                              {hrName}
                            </td>
                          </tr>

                          <tr>
                            <td style={{ padding: "4px 0" }}>
                              <strong>Contact:</strong>
                            </td>
                            <td style={{ padding: "4px 0" }}>
                              {hrContact}
                            </td>
                          </tr>

                          <tr>
                            <td style={{ padding: "4px 0" }}>
                              <strong>Email:</strong>
                            </td>
                            <td style={{ padding: "4px 0" }}>
                              <a
                                href={`mailto:${hrEmail}`}
                                style={{
                                  color: "#1a73e8",
                                  textDecoration: "none",
                                }}
                              >
                                {hrEmail}
                              </a>
                            </td>
                          </tr>
                        </tbody>
                      </table>

                      {/* Next Steps */}
                      <h3
                        style={{
                          marginTop: "30px",
                          color: "#222222",
                        }}
                      >
                        Next Steps
                      </h3>

                      <ol
                        style={{
                          paddingLeft: "20px",
                          margin: "10px 0",
                        }}
                      >
                        <li style={{ marginBottom: "10px" }}>
                          Please confirm your acceptance of the proposed
                          compensation and joining date.
                        </li>

                        <li style={{ marginBottom: "10px" }}>
                          Once we receive your confirmation, we will initiate
                          the preparation of your formal offer letter and share
                          onboarding instructions.
                        </li>

                        <li style={{ marginBottom: "10px" }}>
                          Our HR team will also reach out to coordinate your
                          documentation and pre-joining formalities.
                        </li>
                      </ol>

                      {/* Footer */}
                      <p>
                        Please review the above details and share your
                        confirmation or any questions you may have. We’re
                        excited about the prospect of you joining our PRISM team
                        and contributing to our integration initiatives.
                      </p>

                      <p style={{ marginTop: "30px" }}>
                        <strong>Thank you</strong>
                        <br />
                        BlitzenX - Onboarding Team
                      </p>
                    </td>
                  </tr>
                </tbody>
              </table>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
};

export default OfferConfirmationEmail;