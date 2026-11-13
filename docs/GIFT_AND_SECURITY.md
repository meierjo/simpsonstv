# Gift and network-readiness plan

## Target experience

The recipient should be able to power on the TV, join a new Wi-Fi network, and
receive project updates without learning Linux administration. Normal use must
not expose FTP, a default password, or an internet-facing administration page.

## Service policy

- Keep SSH for maintenance and SFTP file transfer.
- Use `rsync` over SSH; do not run the standalone rsync daemon.
- Remove or disable FTP after the commercial library is staged.
- Change the default `pi` password and use a unique password per TV.
- Prefer SSH keys for the maintainer account.
- Inventory listening ports with `sudo ss -lntup` before gifting.
- Disable services that are not required at boot.
- Keep the TV behind a home router; do not forward SSH from the public internet.

The original Raspberry Pi OS Buster image is obsolete. Short-term hardening is
still valuable, but migration to a supported OS and maintained video backend is
the long-term security fix. That migration must be tested against the Waveshare
display, touch rotation, PWM audio, and gapless playback before replacing a
working gift unit.

## File transfer

Use SFTP or rsync-over-SSH instead of FTP:

```bash
sftp pi@simpsonstv.local
rsync -av --progress commercials/ pi@simpsonstv.local:~/simpsonstv/commercials/
```

The gift unit should have its own hostname, such as `simpsonstv-brother`, to
avoid collisions if multiple TVs appear on one network.

## Wi-Fi onboarding

The onboarding path is a small file named `simpsonstv-wifi.txt` placed on the
SD card's boot partition. A root-owned one-shot service validates the country,
SSID, and password and updates Wi-Fi atomically before networking starts. This
is simpler and safer on the Pi Zero than maintaining a permanent captive
portal. USB onboarding is intentionally not promised because removable drives
are not reliably auto-mounted by the headless Raspberry Pi OS Buster image.

Example file:

```text
country=US
ssid=Example WiFi
password=example password
```

Do not add quotes. Spaces and additional `=` characters in values are
preserved. Unknown keys, duplicate keys, control characters, invalid country
codes, SSIDs outside the 1-32 byte limit, and invalid WPA passphrases are
rejected.

Install the service once:

```bash
cd ~/simpsonstv
sudo cp systemd/tvwifi.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable tvwifi.service
```

To onboard a different network, shut down the Pi, place
`simpsonstv-wifi.txt` at the top level of the card's boot volume from another
computer, return the card, and start the TV. Raspberry Pi OS Buster exposes
that volume as `/boot`.

After a successful import:

- `/boot/simpsonstv-wifi.txt` is removed.
- `/boot/simpsonstv-wifi-result.txt` records success without the password.
- `/etc/wpa_supplicant/wpa_supplicant.conf` contains a derived hexadecimal PSK,
  not the plaintext password.
- The original configuration remains at
  `/etc/wpa_supplicant/wpa_supplicant.conf.simpsonstv-backup` for recovery. The
  first backup is never overwritten by a later import.

If validation or writing fails, the existing Wi-Fi configuration is unchanged,
the request remains available for correction, and the result file reports the
error. Inspect the boot log with:

```bash
sudo journalctl -u tvwifi.service -b --no-pager
```

Security properties:

- Never execute the file as shell code.
- Reject unknown keys and invalid country codes.
- Escape SSIDs and derive WPA PSKs rather than interpolating credentials.
- Preserve the previous working network configuration for recovery.
- Remove or redact the plaintext request after a successful import.
- Run only as a boot-time one-shot; no configuration server listens on the
  network.

## Gift checklist

1. Set a unique hostname and password.
2. Install only the player, touch, button, power-path, and Wi-Fi import units.
3. Disable FTP and any standalone rsync service.
4. Confirm SSH/SFTP works only from the local network.
5. Confirm safe shutdown and recovery after an interrupted boot.
6. Clone a master card only before adding recipient-specific credentials.
7. Keep a tested backup image and written card-recovery instructions.
