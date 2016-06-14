import kel
import pykube


class DeployPlugin(kel.Plugin):

    def provision(self):
        if self.service.routable:
            self.service.setdefault("port", 8000)
        if not self.kubernetes_namespace().exists():
            self.kubernetes_namespace().create()

    def unprovision(self):
        if self.kubernetes_namespace().exists():
            self.kubernetes_namespace().delete()

    @kel.lifecycle(["deployment.create", "deployment.update"])
    def deploy(self, deployment):
        active_deployment = self.kubernetes_deployment()
        if active_deployment is None:
            self.kubernetes_deployment_api_object().create()
        else:
            active_deployment.obj = self.kubernetes_deployment_api_object().obj
            active_deployment.update()

    @property
    def kubernetes_namespace_name(self):
        return "instance-{id}-{kind}".format(
            id=self.service.instance.id,
            kind=self.service.instance.kind
        )

    def kubernetes_namespace(self):
        obj = {
            "kind": "Namespace",
            "apiVersion": "v1",
            "metadata": {
                "name": self.kubernetes_namespace_name,
                "labels": self.kubernetes_labels(),
            }
        }
        return pykube.Namespace(self.kubernetes_api, obj)

    def kubernetes_labels(self):
        return {
            self.label("managed-by"): self.cluster.managed_by,
            self.label("resource-group"): self.service.instance.site.resource_group.name,
            self.label("site"): self.service.instance.site.name,
            self.label("instance"): self.service.instance.name,
            self.label("instance-kind"): self.service.instance.kind,
        }

    def kubernetes_deployment_api_object(self, deployment):
        obj = {
            "kind": "Deployment",
            "apiVersion": "extensions/v1beta1",
            "metadata": {
                "namespace": self.kubernetes_namespace_name,
                "name": self.kubernetes_deployment_name,
                "labels": self.kubernetes_labels(),
            },
            "spec": {
                "replicas": deployment.replicas,
                "selector": {
                    "matchLabels": self.kubernetes_labels(),
                },
                "template": {
                    "metadata": {
                        "labels": self.kubernetes_labels(),
                    },
                    "spec": {
                        "containers": self.kubernetes_containers(deployment),
                    },
                }
            }
        }
        return pykube.Deployment(self.kubernetes_api, obj)

    @property
    def kubernetes_deployment_name(self):
        return self.service.name

    def kubernetes_deployment(self):
        query = pykube.Deployment.objects(self.kubernetes_api, namespace=self.kubernetes_namespace_name)
        return query.get_or_none(name=self.kubernetes_deployment_name)

    def kubernetes_containers(self, deployment):
        containers = []
        variant = self.service.plugin.variant
        if variant == "bundle":
            args = ["start", self.service.name]
        else:
            args = self.service.get("args", [])
        container = {
            "name": self.service.name,
            "image": self.service["image"],
            "imagePullPolicy": "IfNotPresent",
        }
        if args:
            container["args"] = args
        if self.service.routable:
            container.setdefault("ports", []).append({
                "containerPort": self.service["port"],
                "protocol": "TCP",
            })
        containers.append(container)
        return containers
