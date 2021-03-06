# Copyright 2018 Capital One Services, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import six
from collections import namedtuple
from c7n_azure.actions import Tag, AutoTagUser, RemoveTag, TagTrim, TagDelayedAction, DeleteAction
from c7n_azure.filters import (MetricFilter, TagActionFilter,
                               DiagnosticSettingsFilter, PolicyCompliantFilter)
from c7n_azure.provider import resources
from c7n_azure.query import QueryResourceManager, QueryMeta
from c7n_azure.utils import ResourceIdParser

from c7n.utils import local_session


@resources.register('armresource')
@six.add_metaclass(QueryMeta)
class ArmResourceManager(QueryResourceManager):

    class resource_type(object):
        service = 'azure.mgmt.resource'
        client = 'ResourceManagementClient'
        enum_spec = ('resources', 'list', None)
        id = 'id'
        name = 'name'
        diagnostic_settings_enabled = True
        default_report_fields = (
            'name',
            'location',
            'resourceGroup'
        )

    def augment(self, resources):
        for resource in resources:
            if 'id' in resource:
                resource['resourceGroup'] = ResourceIdParser.get_resource_group(resource['id'])
        return resources

    def get_resources(self, resource_ids):
        resource_client = self.get_client('azure.mgmt.resource.ResourceManagementClient')
        session = local_session(self.session_factory)
        data = [
            resource_client.resources.get_by_id(rid, session.resource_api_version(rid))
            for rid in resource_ids
        ]
        return [r.serialize(True) for r in data]

    @staticmethod
    def register_arm_specific(registry, _):
        for resource in registry.keys():
            klass = registry.get(resource)
            if issubclass(klass, ArmResourceManager):
                klass.action_registry.register('tag', Tag)
                klass.action_registry.register('untag', RemoveTag)
                klass.action_registry.register('auto-tag-user', AutoTagUser)
                klass.action_registry.register('tag-trim', TagTrim)
                klass.filter_registry.register('metric', MetricFilter)
                klass.filter_registry.register('marked-for-op', TagActionFilter)
                klass.action_registry.register('mark-for-op', TagDelayedAction)
                klass.filter_registry.register('policy-compliant', PolicyCompliantFilter)

                if resource != 'resourcegroup':
                    klass.action_registry.register('delete', DeleteAction)

                if hasattr(klass.resource_type, 'diagnostic_settings_enabled') \
                        and klass.resource_type.diagnostic_settings_enabled:
                    klass.filter_registry.register('diagnostic-settings', DiagnosticSettingsFilter)


@six.add_metaclass(QueryMeta)
class ChildArmResourceManager(ArmResourceManager):

    ParentSpec = namedtuple("ParentSpec", ["manager_name", "annotate_parent"])

    child_source = 'describe-child-azure'

    @property
    def source_type(self):
        source = self.data.get('source', self.child_source)
        if source == 'describe':
            source = self.child_source
        return source

    def get_parent_manager(self):
        return self.get_resource_manager(self.resource_type.parent_spec.manager_name)


resources.subscribe(resources.EVENT_FINAL, ArmResourceManager.register_arm_specific)
