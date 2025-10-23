# Cloud deployment

## Development instance

The development instance of tarxiv is deployed on the cloud at VirtualData (Université Paris-Saclay). We use a single 8 vCPU instance (`vd.8`) running AlmaLinux 9:

```bash
openstack server create \
    --image abdcf647-f7a7-486f-a559-32862b3e61e4 \
    --flavor vd.8 \
    --key <whatever> \
    --availability-zone nova \
    tarxiv-dev
```

When it is active, ssh to it and update packages:

```bash
sudo dnf update
```

The update is important to start with up-to-date packages as the image could be old (I got problems with old openssl version). Finally install some useful utilities:

```bash
dnf install epel-release
dnf install git htop wget net-tools
```

The system disk is small (20GB), so an additional storage space can be mounted (200GB) to host data. On your laptop/desktop:

```bash
# create
openstack volume create \
    --size 200 \
    tarxiv-volume

# attach
openstack server add volume tarxiv-dev tarxiv-volume
```

On the VM, mount the volume (check with `df -h` where the volume has been attached, and change `/dev/vdbX` accordingly):

```bash
fdisk -l /dev/vdb
parted /dev/vdb mklabel gpt
parted --align none /dev/vdb -- mkpart primary xfs 0 -1
mkfs.xfs /dev/vdb1
mkdir /data
mount /dev/vdb1 /data
data=$(blkid|grep /dev/vdb1|cut -d " " -f 2)
cat >> /etc/fstab << EOF
$data        /data   xfs    defaults,nofail        0       0
EOF
```

Then on the VM, create a python virtual environment:

```bash
cd /data
python -m venv tarxivenv 
```

and update the `.bash_profile` to get it at log-in:

```bash
# in ~/.bash_profile

# Make the prompt yellow fancy
unset rc
export PS1="\[$(tput bold)\[\[\e[1;93m\]\u@\h \W]\$ \[\e[m\]\[$(tput sgr0)"

source /data/tarxivenv/bin/activate
```

Install the firewall, and enable it:

```bash
# as root
dnf install firewalld
systemctl enable firewalld
systemctl start firewalld
```

and add some rules:

```bash
# as root
firewall-cmd --permanent --zone=public --add-service=https
firewall-cmd --permanent --zone=public --add-service=ssh

firewall-cmd --reload
```

Also install `fail2ban`:

```bash
# as root
dnf install fail2ban
```

Create the property file at `/etc/fail2ban/jail.local`:

```bash
[DEFAULT]
bantime = 86400
banaction = iptables-multiport
[sshd]
enabled = true
```

and activate the service:

```bash
systemctl enable fail2ban
systemctl start fail2ban
systemctl status fail2ban
```

Finally tell docker to put his images somewhere else than in the disk system:

```bash
# as root
systemctl stop docker
mkdir /data/docker
rsync -aqxP /var/lib/docker/ /data/docker
rm -rf /var/lib/docker
ln -s /data/docker /var/lib/docker
systemctl start docker
```

Done!
