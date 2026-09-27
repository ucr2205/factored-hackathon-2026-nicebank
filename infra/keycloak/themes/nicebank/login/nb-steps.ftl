<#-- Password recovery progress (Usuario -> Verificar -> Contraseña), same pattern as the reference login. -->
<#macro bar active>
    <ol class="nb-steps" aria-label="${msg("nbRecoverTitle")}">
        <#list ["nbStepUser", "nbStepVerify", "nbStepPassword"] as key>
            <#assign n = key?index + 1>
            <li class="<#if n lt active>done<#elseif n == active>active</#if>"<#if n == active> aria-current="step"</#if>>
                <span class="nb-step-dot"><#if n lt active>&#10003;<#else>${n}</#if></span>
                <span class="nb-step-label">${msg(key)}</span>
            </li>
        </#list>
    </ol>
</#macro>
