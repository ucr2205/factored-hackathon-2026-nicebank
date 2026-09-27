<#macro emailLayout>
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#faf7f8;font-family:Montserrat,Segoe UI,Arial,sans-serif;color:#23161b;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#faf7f8;padding:32px 12px;">
    <tr><td align="center">
      <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background:#ffffff;border-radius:18px;overflow:hidden;border-top:4px solid #7a1f3d;">
        <tr><td style="background:#7a1f3d;padding:22px 28px;color:#ffffff;font-size:20px;font-weight:800;">NiceBank</td></tr>
        <tr><td style="padding:28px;font-size:15px;line-height:1.6;">
          <#nested>
        </td></tr>
        <tr><td style="padding:16px 28px 24px;font-size:12px;color:#6e5a62;border-top:1px solid #efe3e7;">
          ${msg("nbEmailFooter")}
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
</#macro>
