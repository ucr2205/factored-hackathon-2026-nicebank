<#-- Lucide icons (https://lucide.dev, ISC license) as inline SVG, so the Keycloak pages match the React app. -->
<#macro i name size=18 cls="">
<svg class="nb-icon ${cls}" xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
<#switch name>
    <#case "shield-check"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/><#break>
    <#case "key-round"><path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z"/><circle cx="16.5" cy="7.5" r=".5" fill="currentColor"/><#break>
    <#case "message-circle-off"><path d="m2 2 20 20"/><path d="M4.93 4.929a10 10 0 0 0-1.938 11.412 2 2 0 0 1 .094 1.167l-1.065 3.29a1 1 0 0 0 1.236 1.168l3.413-.998a2 2 0 0 1 1.099.092 10 10 0 0 0 11.302-1.989"/><path d="M8.35 2.69A10 10 0 0 1 21.3 15.65"/><#break>
    <#case "globe"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/><#break>
    <#case "chevron-down"><path d="m6 9 6 6 6-6"/><#break>
    <#case "check"><path d="M20 6 9 17l-5-5"/><#break>
    <#case "life-buoy"><circle cx="12" cy="12" r="10"/><path d="m4.93 4.93 4.24 4.24"/><path d="m14.83 9.17 4.24-4.24"/><path d="m14.83 14.83 4.24 4.24"/><path d="m9.17 14.83-4.24 4.24"/><circle cx="12" cy="12" r="4"/><#break>
    <#case "circle-alert"><circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/><#break>
    <#case "circle-check"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/><#break>
    <#case "info"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/><#break>
    <#case "rotate-ccw"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><#break>
    <#case "mail"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/><#break>
    <#case "arrow-left"><path d="m12 19-7-7 7-7"/><path d="M19 12H5"/><#break>
    <#case "smartphone"><rect width="14" height="20" x="5" y="2" rx="2" ry="2"/><path d="M12 18h.01"/><#break>
    <#default><circle cx="12" cy="12" r="10"/>
</#switch>
</svg>
</#macro>
