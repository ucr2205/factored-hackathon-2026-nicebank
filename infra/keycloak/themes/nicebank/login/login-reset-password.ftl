<#-- NiceBank step 1 of password recovery: identify the user; Keycloak emails a single-use link. -->
<#import "template.ftl" as layout>
<#import "nb-steps.ftl" as steps>
<#import "nb-icons.ftl" as ic>
<@layout.registrationLayout displayInfo=false displayMessage=!messagesPerField.existsError('username'); section>
    <#if section = "header">
        ${msg("nbRecoverTitle")}
    <#elseif section = "form">
        <@steps.bar active=1/>
        <p class="nb-otp-hint">${msg("nbRecoverHint")}</p>
        <form id="kc-reset-password-form" action="${url.loginAction}" method="post">
            <div>
                <label for="username">${msg("username")}</label>
                <input type="text" id="username" name="username" autofocus autocomplete="username"
                       value="${(auth.attemptedUsername!'')}" placeholder="${msg("nbUsernamePlaceholder")}"
                       aria-invalid="<#if messagesPerField.existsError('username')>true</#if>" dir="ltr"/>
                <#if messagesPerField.existsError('username')>
                    <span id="input-error-username" aria-live="polite">${kcSanitize(messagesPerField.get('username'))?no_esc}</span>
                </#if>
            </div>
            <div class="nb-demo-note"><@ic.i name="mail" size=16/><span>${kcSanitize(msg("nbDemoMailbox"))?no_esc}</span></div>
            <div id="kc-form-buttons">
                <input type="submit" value="${msg("nbSendLink")}"/>
            </div>
            <div class="nb-back"><a href="${url.loginUrl}"><@ic.i name="arrow-left" size=14/> ${msg("nbBackToLogin")}</a></div>
        </form>
    </#if>
</@layout.registrationLayout>
