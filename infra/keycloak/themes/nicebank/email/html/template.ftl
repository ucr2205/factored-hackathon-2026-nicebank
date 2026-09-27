<#-- Same design as the backend notifications (backend/internal/notify/templates/layout.html): dark card,
     accent line and title, security note and dark footer. accent: title/button color for this email. -->
<#macro emailLayout accent="#E5769A">
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="dark">
</head>
<body style="margin:0;padding:0;background-color:#121212;font-family:'Segoe UI',Arial,Helvetica,sans-serif;color:#ffffff;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#121212;margin:0;padding:0;">
    <tr>
      <td align="center" style="padding:40px 12px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
          style="max-width:600px;background-color:#1E1E1E;border:1px solid #333333;border-radius:12px;box-shadow:0 8px 16px rgba(0,0,0,0.4);margin:0 auto;overflow:hidden;">
          <tr>
            <td align="center" style="padding:28px 20px 22px;background-color:#252525;border-bottom:3px solid ${accent};">
              <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="width:38px;height:38px;background-color:#7A1F3D;border-radius:10px;text-align:center;vertical-align:middle;font-size:22px;font-weight:bold;color:#ffffff;">N</td>
                  <td style="padding-left:12px;font-size:24px;font-weight:bold;color:#ffffff;letter-spacing:0.5px;">Nice<span style="color:#E5769A;">Bank</span></td>
                </tr>
              </table>
            </td>
          </tr>
          <#nested>
          <tr>
            <td style="padding:24px 32px 32px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="padding:14px 16px;background-color:#171717;border-left:4px solid #E5769A;border-radius:6px;font-size:13px;line-height:1.5;color:#bbbbbb;">
                    <strong style="color:#E5769A;">${msg("nbEmailSecurityLabel")}</strong> ${msg("nbEmailSecurity")}
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td align="center" style="padding:20px 30px;background-color:#171717;border-top:1px solid #333333;">
              <p style="margin:0 0 10px;font-size:13px;color:#888888;">${msg("nbEmailThanks")} <span style="color:#E5769A;font-weight:bold;">NiceBank</span>.</p>
              <p style="margin:0;font-size:12px;line-height:1.5;color:#666666;">${msg("nbEmailFooter")}</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
</#macro>
