# Generated migration for performance monitoring models

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('meetings', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PerformanceMetric',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('metric_type', models.CharField(choices=[('call_bot_session', 'Call Bot Session'), ('ai_processing', 'AI Processing'), ('crm_sync', 'CRM Sync'), ('validation_session', 'Validation Session'), ('database_query', 'Database Query'), ('api_request', 'API Request'), ('system_resource', 'System Resource')], db_index=True, max_length=50)),
                ('metric_name', models.CharField(db_index=True, max_length=200)),
                ('value', models.FloatField()),
                ('unit', models.CharField(default='seconds', max_length=50)),
                ('status', models.CharField(choices=[('success', 'Success'), ('warning', 'Warning'), ('error', 'Error'), ('timeout', 'Timeout')], default='success', max_length=20)),
                ('object_id', models.PositiveIntegerField(blank=True, null=True)),
                ('metadata', models.JSONField(default=dict)),
                ('error_message', models.TextField(blank=True)),
                ('timestamp', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('start_time', models.DateTimeField(blank=True, null=True)),
                ('end_time', models.DateTimeField(blank=True, null=True)),
                ('content_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='CallBotPerformance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('connection_time', models.FloatField(help_text='Time to connect to call in seconds')),
                ('connection_attempts', models.IntegerField(default=1)),
                ('connection_success', models.BooleanField(default=True)),
                ('audio_quality_score', models.FloatField(blank=True, help_text='Audio quality score 0-1', null=True)),
                ('audio_dropouts', models.IntegerField(default=0)),
                ('audio_latency', models.FloatField(blank=True, help_text='Audio latency in ms', null=True)),
                ('transcription_accuracy', models.FloatField(blank=True, help_text='Transcription accuracy 0-1', null=True)),
                ('transcription_latency', models.FloatField(blank=True, help_text='Transcription latency in seconds', null=True)),
                ('words_per_minute', models.FloatField(blank=True, null=True)),
                ('error_count', models.IntegerField(default=0)),
                ('reconnection_count', models.IntegerField(default=0)),
                ('cpu_usage_avg', models.FloatField(blank=True, help_text='Average CPU usage percentage', null=True)),
                ('memory_usage_avg', models.FloatField(blank=True, help_text='Average memory usage in MB', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('call_bot_session', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='performance_metrics', to='meetings.callbotsession')),
            ],
        ),
        migrations.CreateModel(
            name='AIProcessingPerformance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('operation_type', models.CharField(choices=[('transcription', 'Transcription'), ('summary_generation', 'Summary Generation'), ('action_item_extraction', 'Action Item Extraction'), ('crm_suggestion', 'CRM Suggestion'), ('validation_questions', 'Validation Questions')], db_index=True, max_length=50)),
                ('operation_id', models.CharField(db_index=True, max_length=200)),
                ('processing_time', models.FloatField(help_text='Processing time in seconds')),
                ('input_size', models.IntegerField(help_text='Input size in characters/tokens')),
                ('output_size', models.IntegerField(help_text='Output size in characters/tokens')),
                ('confidence_score', models.FloatField(blank=True, help_text='AI confidence score 0-1', null=True)),
                ('accuracy_score', models.FloatField(blank=True, help_text='Measured accuracy 0-1', null=True)),
                ('tokens_used', models.IntegerField(blank=True, null=True)),
                ('api_cost', models.DecimalField(blank=True, decimal_places=6, max_digits=10, null=True)),
                ('error_occurred', models.BooleanField(default=False)),
                ('error_type', models.CharField(blank=True, max_length=100)),
                ('retry_count', models.IntegerField(default=0)),
                ('model_version', models.CharField(blank=True, max_length=100)),
                ('parameters', models.JSONField(default=dict)),
                ('timestamp', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='SystemAlert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('alert_type', models.CharField(choices=[('performance_degradation', 'Performance Degradation'), ('high_error_rate', 'High Error Rate'), ('system_failure', 'System Failure'), ('resource_exhaustion', 'Resource Exhaustion'), ('api_rate_limit', 'API Rate Limit'), ('connection_failure', 'Connection Failure')], db_index=True, max_length=50)),
                ('severity', models.CharField(choices=[('info', 'Info'), ('warning', 'Warning'), ('error', 'Error'), ('critical', 'Critical')], db_index=True, max_length=20)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('component', models.CharField(db_index=True, max_length=100)),
                ('metric_threshold', models.FloatField(blank=True, null=True)),
                ('current_value', models.FloatField(blank=True, null=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('acknowledged', models.BooleanField(default=False)),
                ('acknowledged_by', models.CharField(blank=True, max_length=200)),
                ('acknowledged_at', models.DateTimeField(blank=True, null=True)),
                ('resolved', models.BooleanField(default=False)),
                ('resolved_by', models.CharField(blank=True, max_length=200)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('resolution_notes', models.TextField(blank=True)),
                ('first_occurred', models.DateTimeField(default=django.utils.timezone.now)),
                ('last_occurred', models.DateTimeField(default=django.utils.timezone.now)),
                ('occurrence_count', models.IntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-severity', '-first_occurred'],
            },
        ),
        migrations.CreateModel(
            name='PerformanceThreshold',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('metric_type', models.CharField(db_index=True, max_length=50)),
                ('metric_name', models.CharField(db_index=True, max_length=200)),
                ('warning_threshold', models.FloatField(blank=True, null=True)),
                ('error_threshold', models.FloatField(blank=True, null=True)),
                ('critical_threshold', models.FloatField(blank=True, null=True)),
                ('comparison_operator', models.CharField(choices=[('>', 'Greater than'), ('<', 'Less than'), ('=', 'Equal to')], default='>', max_length=10)),
                ('time_window', models.IntegerField(default=300, help_text='Time window in seconds')),
                ('min_occurrences', models.IntegerField(default=1, help_text='Minimum occurrences to trigger alert')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='ConcurrentCallMetrics',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('active_calls', models.IntegerField(default=0)),
                ('max_concurrent_calls', models.IntegerField(default=0)),
                ('successful_connections', models.IntegerField(default=0)),
                ('failed_connections', models.IntegerField(default=0)),
                ('avg_connection_time', models.FloatField(blank=True, null=True)),
                ('avg_processing_time', models.FloatField(blank=True, null=True)),
                ('avg_memory_usage', models.FloatField(blank=True, null=True)),
                ('avg_cpu_usage', models.FloatField(blank=True, null=True)),
                ('system_load', models.FloatField(blank=True, null=True)),
                ('available_memory', models.FloatField(blank=True, null=True)),
                ('disk_usage', models.FloatField(blank=True, null=True)),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='performancemetric',
            index=models.Index(fields=['metric_type', 'timestamp'], name='performance_metric_type_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='performancemetric',
            index=models.Index(fields=['metric_name', 'timestamp'], name='performance_metric_name_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='performancemetric',
            index=models.Index(fields=['status', 'timestamp'], name='performance_metric_status_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='performancemetric',
            index=models.Index(fields=['timestamp'], name='performance_metric_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='callbotperformance',
            index=models.Index(fields=['connection_success', 'created_at'], name='callbot_performance_success_created_idx'),
        ),
        migrations.AddIndex(
            model_name='callbotperformance',
            index=models.Index(fields=['transcription_accuracy'], name='callbot_performance_transcription_accuracy_idx'),
        ),
        migrations.AddIndex(
            model_name='callbotperformance',
            index=models.Index(fields=['error_count'], name='callbot_performance_error_count_idx'),
        ),
        migrations.AddIndex(
            model_name='aiprocessingperformance',
            index=models.Index(fields=['operation_type', 'timestamp'], name='ai_performance_operation_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='aiprocessingperformance',
            index=models.Index(fields=['processing_time'], name='ai_performance_processing_time_idx'),
        ),
        migrations.AddIndex(
            model_name='aiprocessingperformance',
            index=models.Index(fields=['confidence_score'], name='ai_performance_confidence_score_idx'),
        ),
        migrations.AddIndex(
            model_name='aiprocessingperformance',
            index=models.Index(fields=['error_occurred', 'timestamp'], name='ai_performance_error_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='systemalert',
            index=models.Index(fields=['alert_type', 'is_active'], name='system_alert_type_active_idx'),
        ),
        migrations.AddIndex(
            model_name='systemalert',
            index=models.Index(fields=['severity', 'is_active'], name='system_alert_severity_active_idx'),
        ),
        migrations.AddIndex(
            model_name='systemalert',
            index=models.Index(fields=['component', 'is_active'], name='system_alert_component_active_idx'),
        ),
        migrations.AddIndex(
            model_name='systemalert',
            index=models.Index(fields=['first_occurred'], name='system_alert_first_occurred_idx'),
        ),
        migrations.AddIndex(
            model_name='performancethreshold',
            index=models.Index(fields=['metric_type', 'is_active'], name='performance_threshold_type_active_idx'),
        ),
        migrations.AddIndex(
            model_name='concurrentcallmetrics',
            index=models.Index(fields=['timestamp'], name='concurrent_call_metrics_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='concurrentcallmetrics',
            index=models.Index(fields=['active_calls'], name='concurrent_call_metrics_active_calls_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='performancethreshold',
            unique_together={('metric_type', 'metric_name')},
        ),
    ]