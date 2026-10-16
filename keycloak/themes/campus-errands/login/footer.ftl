<#macro content>
    <#if pageId == "login" && realm.registrationAllowed && !registrationDisabled??>
        <p class="foc-footer">New to Campus Errands? <a href="${url.registrationUrl}">Create an account</a></p>
    <#else>
        <p class="foc-footer"><a href="${properties.focAppUrl!'/'}">Back to Campus Errands</a></p>
    </#if>
</#macro>
