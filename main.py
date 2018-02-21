import logging
import sys
import time

import click

from autoscaler.cluster import Cluster
from autoscaler.notification import Notifier

logger = logging.getLogger('autoscaler')

DEBUG_LOGGING_MAP = {
    0: logging.CRITICAL,
    1: logging.WARNING,
    2: logging.INFO,
    3: logging.DEBUG
}

@click.command()
@click.option("--resource-group", help='name of the resource group hosting the acs-engine cluster')
@click.option("--acs-deployment", help='name of the deployment in acs (default=azuredeploy)', default='azuredeploy')
@click.option("--sleep", default=60, help='time in seconds between successive checks')
@click.option("--kubeconfig", default=None,
              help='Full path to kubeconfig file. If not provided, '
                   'we assume that we\'re running on kubernetes.')
#How many agents should we keep even if the cluster is not utilized? The autoscaler will currenty break if --spare-agents == 0
@click.option("--spare-agents", default=1, help='number of agent per pool that should always stay up') 
@click.option("--idle-threshold", default=1800, help='time in seconds an agent can stay idle')
@click.option("--service-principal-app-id", default=None, envvar='AZURE_SP_APP_ID')
@click.option("--service-principal-secret", default=None, envvar='AZURE_SP_SECRET')
@click.option("--service-principal-tenant-id", default=None, envvar='AZURE_SP_TENANT_ID')
@click.option("--subscription-id", default=None, envvar='SUBSCRIPTION_ID')
@click.option("--kubeconfig-private-key", default=None, envvar='KUBECONFIG_PRIVATE_KEY')
@click.option("--client-private-key", default=None, envvar='CLIENT_PRIVATE_KEY')
@click.option("--ca-private-key", default=None, envvar='CA_PRIVATE_KEY')
@click.option("--etcd-client-private-key", default=None, envvar='ETCD_CLIENT_PRIVATE_KEY')
@click.option("--etcd-server-private-key", default=None, envvar='ETCD_SERVER_PRIVATE_KEY')
@click.option("--etcd-peer-private-key-0", default=None, envvar='ETCD_PEER_PRIVATE_KEY_0')
@click.option("--no-scale", is_flag=True)
@click.option("--over-provision", default=0)
@click.option("--no-maintenance", is_flag=True)
@click.option("--ignore-pools", default='', help='list of pools that should be ignored by the autoscaler, delimited by a comma')
@click.option("--slack-hook", default=None, envvar='SLACK_HOOK',
              help='Slack webhook URL. If provided, post scaling messages '
                   'to Slack.')
@click.option("--dry-run", is_flag=True)
@click.option('--verbose', '-v',
              help="Sets the debug noise level, specify multiple times "
                   "for more verbosity.",
              type=click.IntRange(0, 3, clamp=True),
              count=True, default=2)
#Debug mode will explicitly surface erros
@click.option("--debug", is_flag=True) 
def main(resource_group, acs_deployment, sleep, kubeconfig,
         service_principal_app_id, service_principal_secret, subscription_id, 
         kubeconfig_private_key, client_private_key, ca_private_key,
         etcd_client_private_key, etcd_server_private_key, etcd_peer_private_key_0
         service_principal_tenant_id, spare_agents, idle_threshold,
         no_scale, over_provision, no_maintenance, ignore_pools, slack_hook,
         dry_run, verbose, debug):
    logger_handler = logging.StreamHandler(sys.stderr)
    logger_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(logger_handler)
    logger.setLevel(DEBUG_LOGGING_MAP.get(verbose, logging.CRITICAL))

    if not (service_principal_app_id and service_principal_secret and service_principal_tenant_id and subscription_id):
        logger.error("Missing Azure credentials. Please provide service_principal_app_id, service_principal_secret, service_principal_tenant_id and subscription_id.")
        sys.exit(1)
    
    if not client_private_key:
        logger.error('Missing client_private_key. Provide it through --client-private-key or CLIENT_PRIVATE_KEY environment variable')
    
    if not kubeconfig_private_key:
        logger.error('Missing kubeconfig_private_key. Provide it through --kubeconfig-private-key or KUBECONFIG_PRIVATE_KEY environment variable')
    
    if not ca_private_key:
        logger.error('Missing ca_private_key. Provide it through --ca-private-key or CA_PRIVATE_KEY environment variable')
    
    if not etcd_peer_private_key_0:
        logger.error('Missing etcd_peer_private_key_0. Provide it through --etcd_peer_private_key_0 or ETCD_PEER_PRIVATE_KEY_0 environment variable')
    
    
    notifier = None
    if slack_hook:
        notifier = Notifier(slack_hook)

    instance_init_time = 600
    
    cluster = Cluster(kubeconfig=kubeconfig,
                      instance_init_time=instance_init_time,
                      spare_agents=spare_agents,
                      idle_threshold=idle_threshold,
                      resource_group=resource_group,
                      acs_deployment=acs_deployment,
                      service_principal_app_id=service_principal_app_id,
                      service_principal_secret=service_principal_secret,
                      service_principal_tenant_id=service_principal_tenant_id,
                      subscription_id=subscription_id,
                      kubeconfig_private_key=kubeconfig_private_key,
                      client_private_key=client_private_key,
                      ca_private_key=ca_private_key,
                      etcd_client_private_key=etcd_client_private_key,
                      etcd_server_private_key=etcd_server_private_key,
                      etcd_peer_private_key_0=etcd_peer_private_key_0,
                      scale_up=not no_scale,
                      ignore_pools=ignore_pools,
                      maintainance=not no_maintenance,
                      over_provision=over_provision,
                      notifier=notifier,
                      dry_run=dry_run,
                      )
    cluster.login()
    backoff = sleep
    while True:
        scaled = cluster.loop(debug)
        if scaled:
            time.sleep(sleep)
            backoff = sleep
        else:
            logger.warn("backoff: %s" % backoff)
            backoff *= 2
            time.sleep(backoff)


if __name__ == "__main__":
    main()
