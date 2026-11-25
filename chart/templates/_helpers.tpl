{{/*
Expand the name of the chart.
*/}}
{{- define "ana-automation-ui.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "ana-automation-ui.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "ana-automation-ui.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "ana-automation-ui.labels" -}}
helm.sh/chart: {{ include "ana-automation-ui.chart" . }}
{{ include "ana-automation-ui.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "ana-automation-ui.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ana-automation-ui.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Redis fullname. "-redis" is appended after truncating to 57, so the result stays within 63.
*/}}
{{- define "ana-automation-ui.redis.fullname" -}}
{{- printf "%s-redis" (include "ana-automation-ui.fullname" . | trunc 57 | trimSuffix "-") }}
{{- end }}

{{/*
Redis selector labels. The pod template carries only these, so a chart release that leaves
Redis unchanged does not restart it and sign everyone out. The "-redis" name keeps its pods out
of the portal Service selector, which matches on name and instance alone.
*/}}
{{- define "ana-automation-ui.redis.selectorLabels" -}}
app.kubernetes.io/name: {{ printf "%s-redis" (include "ana-automation-ui.name" . | trunc 57 | trimSuffix "-") }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: redis
{{- end }}

{{/*
Redis labels for the Deployment and Service metadata.
*/}}
{{- define "ana-automation-ui.redis.labels" -}}
helm.sh/chart: {{ include "ana-automation-ui.chart" . }}
{{ include "ana-automation-ui.redis.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
