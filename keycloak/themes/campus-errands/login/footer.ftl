<#macro content>
    <#if pageId == "login">
        <p class="foc-footer">New to Campus Errands? <a href="${properties.focAppUrl!'/'}/sign-up">Create an account</a></p>
    <#else>
        <p class="foc-footer"><a href="${properties.focAppUrl!'/'}">Back to Campus Errands</a></p>
    </#if>
</#macro>
