<#import "template.ftl" as layout>
<@layout.emailLayout accent="#E5769A">
  <tr>
    <td align="center" style="padding:36px 30px 6px;">
      <h1 style="margin:0;font-size:24px;line-height:1.3;font-weight:bold;color:#E5769A;text-transform:uppercase;letter-spacing:0.5px;">${msg("nbEmailResetTitle")}</h1>
      <p style="margin:10px 0 0;font-size:15px;color:#aaaaaa;">${msg("nbEmailResetSubtitle")}</p>
    </td>
  </tr>
  <tr>
    <td style="padding:22px 32px 8px;">
      <p style="margin:0 0 18px;font-size:16px;line-height:1.6;color:#e0e0e0;">${msg("nbEmailHello")}</p>
      <p style="margin:0 0 24px;font-size:16px;line-height:1.6;color:#e0e0e0;">${msg("nbEmailResetIntro", linkExpirationFormatter(linkExpiration))}</p>
      <table role="presentation" width="100%" cellpadding="14" cellspacing="0" border="0"
        style="background-color:#2A2A2A;border-radius:8px;border:1px solid #3A3A3A;">
        <tr>
          <td style="font-size:14px;line-height:1.5;color:#E5769A;text-align:center;">
            <strong>${msg("nbEmailImportant")}</strong> ${msg("nbEmailResetIgnore")}
          </td>
        </tr>
      </table>
    </td>
  </tr>
  <tr>
    <td align="center" style="padding:28px 32px 8px;">
      <a href="${link}" style="display:inline-block;padding:14px 30px;background-color:#E5769A;color:#121212;font-size:15px;font-weight:bold;text-decoration:none;border-radius:6px;text-transform:uppercase;letter-spacing:0.5px;">${msg("nbEmailResetButton")}</a>
    </td>
  </tr>
</@layout.emailLayout>
