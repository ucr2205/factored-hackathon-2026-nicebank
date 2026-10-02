<#-- NiceBank login layout: animated brand panel on the left, access card on the right (stacks on mobile).
     Keeps the base theme's section contract (header, show-username, form, socialProviders, info),
     so every Keycloak login page (login, OTP, logout confirm, recovery, errors) renders inside it. -->
<#import "nb-icons.ftl" as ic>
<#assign nbLangNames = {"es": "Español", "pt-BR": "Português", "en": "English"}>
<#assign nbLangCodes = {"es": "ES", "pt-BR": "PT", "en": "EN"}>
<#macro registrationLayout bodyClass="" displayInfo=false displayMessage=true displayRequiredFields=false others...>
<!DOCTYPE html>
<html<#if realm.internationalizationEnabled> lang="${locale.currentLanguageTag}"</#if>>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="noindex, nofollow">
    <#-- Inside the app's step-up dialog (an iframe of NiceBank's own origins), show only the access card. -->
    <script>if (window.self !== window.top) document.documentElement.classList.add("nb-embedded");</script>
    <title>${msg("loginTitle",(realm.displayName!''))}</title>
    <link rel="icon" type="image/png" href="${url.resourcesPath}/img/nicebank-mark.png" />
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <#if properties.styles?has_content>
        <#list properties.styles?split(' ') as style>
            <link href="${url.resourcesPath}/${style}" rel="stylesheet" />
        </#list>
    </#if>
    <script type="importmap">
        { "imports": { "rfc4648": "${url.resourcesCommonPath}/vendor/rfc4648/rfc4648.js" } }
    </script>
    <script src="${url.resourcesPath}/js/menu-button-links.js" type="module"></script>
    <#if scripts??>
        <#list scripts as script>
            <script src="${script}" type="text/javascript"></script>
        </#list>
    </#if>
    <script type="module">
        import { startSessionPolling } from "${url.resourcesPath}/js/authChecker.js";
        startSessionPolling("${url.ssoLoginInOtherTabsUrl?no_esc}");
    </script>
</head>

<body class="nb-body ${bodyClass}">
<div class="nb-shell">
    <aside class="nb-brand">
        <div class="nb-aurora" aria-hidden="true">
            <span class="nb-orb nb-orb-1"></span>
            <span class="nb-orb nb-orb-2"></span>
            <span class="nb-orb nb-orb-3"></span>
            <span class="nb-orb nb-orb-4"></span>
            <span class="nb-sheen"></span>
        </div>

        <div class="nb-logo nb-rise">
            <img src="${url.resourcesPath}/img/nicebank-mark.png" alt="" width="44" height="44">
            <span>NiceBank</span>
        </div>

        <div class="nb-pitch">
            <h1 class="nb-rise nb-d1">${msg("nbHeadline")}</h1>
            <p class="nb-rise nb-d2">${msg("nbSubtitle")}</p>
            <ul class="nb-trust">
                <li class="nb-rise nb-d3"><span class="nb-trust-icon"><@ic.i name="shield-check" size=16/></span>${msg("nbTrustSecure")}</li>
                <li class="nb-rise nb-d4"><span class="nb-trust-icon"><@ic.i name="key-round" size=16/></span>${msg("nbTrustStepUp")}</li>
                <li class="nb-rise nb-d5"><span class="nb-trust-icon"><@ic.i name="message-circle-off" size=16/></span>${msg("nbTrustNever")}</li>
            </ul>
        </div>

        <p class="nb-footer nb-rise nb-d5">&copy; 2026 NiceBank &middot; ${msg("nbFictional")}</p>
    </aside>

    <main class="nb-access">
        <#if realm.internationalizationEnabled && locale.supported?size gt 1>
            <div id="kc-locale" class="nb-locale">
                <div id="kc-locale-dropdown" class="menu-button-links">
                    <button tabindex="1" id="kc-current-locale-link" aria-label="${msg("languages")}" aria-haspopup="true"
                            aria-expanded="false" aria-controls="language-switch1">
                        <@ic.i name="globe" size=16/>
                        <span>${nbLangCodes[locale.currentLanguageTag]!locale.current}</span>
                        <@ic.i name="chevron-down" size=14 cls="nb-caret"/>
                    </button>
                    <ul role="menu" tabindex="-1" aria-labelledby="kc-current-locale-link" id="language-switch1">
                        <#list locale.supported as l>
                            <li role="none">
                                <a role="menuitem" href="${l.url}"<#if l.languageTag == locale.currentLanguageTag> aria-current="true"</#if>>
                                    <span class="nb-lang-code">${nbLangCodes[l.languageTag]!l.languageTag}</span>
                                    <span class="nb-lang-name">${nbLangNames[l.languageTag]!l.label}</span>
                                    <#if l.languageTag == locale.currentLanguageTag><@ic.i name="check" size=16 cls="nb-lang-check"/></#if>
                                </a>
                            </li>
                        </#list>
                    </ul>
                </div>
            </div>
        </#if>

        <section class="nb-card nb-card-enter">
            <header class="nb-card-header">
                <#if !(auth?has_content && auth.showUsername() && !auth.showResetCredentials())>
                    <h2 id="kc-page-title"><#nested "header"></h2>
                <#else>
                    <#nested "show-username">
                    <h2 id="kc-page-title"><#nested "header"></h2>
                    <div id="kc-username" class="nb-attempted">
                        <span id="kc-attempted-username">${auth.attemptedUsername}</span>
                        <a id="reset-login" href="${url.loginRestartFlowUrl}"><@ic.i name="rotate-ccw" size=14/> ${msg("restartLoginTooltip")}</a>
                    </div>
                </#if>
            </header>

            <#if displayMessage && message?has_content && (message.type != 'warning' || !isAppInitiatedAction??)>
                <div class="nb-alert nb-alert-${message.type}" role="alert">
                    <#if message.type = 'error'><@ic.i name="circle-alert" size=18/>
                    <#elseif message.type = 'success'><@ic.i name="circle-check" size=18/>
                    <#else><@ic.i name="info" size=18/></#if>
                    <span>${kcSanitize(message.summary)?no_esc}</span>
                </div>
            </#if>

            <#nested "form">

            <#if auth?has_content && auth.showTryAnotherWayLink()>
                <form id="kc-select-try-another-way-form" action="${url.loginAction}" method="post">
                    <input type="hidden" name="tryAnotherWay" value="on"/>
                    <a href="#" id="try-another-way"
                       onclick="document.forms['kc-select-try-another-way-form'].requestSubmit();return false;">${msg("doTryAnotherWay")}</a>
                </form>
            </#if>

            <#nested "socialProviders">

            <#if displayInfo>
                <div id="kc-info" class="nb-info"><#nested "info"></div>
            </#if>
        </section>

        <p class="nb-help"><@ic.i name="life-buoy" size=14/> ${msg("nbHelp")}</p>
    </main>
</div>
</body>
</html>
</#macro>
