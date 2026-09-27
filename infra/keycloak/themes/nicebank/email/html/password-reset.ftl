<#import "template.ftl" as layout>
<@layout.emailLayout>
  <h1 style="margin:0 0 12px;font-size:22px;color:#7a1f3d;">${msg("nbEmailResetTitle")}</h1>
  <p style="margin:0 0 20px;">${msg("nbEmailResetIntro", linkExpirationFormatter(linkExpiration))}</p>
  <p style="margin:0 0 24px;">
    <a href="${link}" style="display:inline-block;background:#7a1f3d;color:#ffffff;text-decoration:none;font-weight:700;padding:12px 26px;border-radius:999px;">${msg("nbEmailResetButton")}</a>
  </p>
  <p style="margin:0;font-size:13px;color:#6e5a62;">${msg("nbEmailResetIgnore")}</p>
</@layout.emailLayout>
