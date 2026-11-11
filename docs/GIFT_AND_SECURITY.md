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

## Wi-Fi onboarding design

The planned onboarding path is a small file named `simpsonstv-wifi.txt` placed
on a USB drive or the SD card's boot partition. A root-owned one-shot service
will validate the country, SSID, and password, update Wi-Fi atomically, archive
the request without retaining the password, and reboot. This is simpler and
safer on the Pi Zero than maintaining a permanent captive portal.

Example file:

```text
country=US
ssid=Example WiFi
password=example password
```

Implementation requirements:

- Never execute the file as shell code.
- Reject unknown keys and invalid country codes.
- Escape values for `wpa_supplicant.conf` rather than interpolating blindly.
- Preserve the previous working network configuration for recovery.
- Remove or redact the plaintext request after a successful import.
- Show success or failure on the TV screen.
- Allow the import service to run only at boot or by an explicit Touch Tuner
  action; do not leave a network configuration server listening continuously.

## Gift checklist

1. Set a unique hostname and password.
2. Install only the player, touch, button, power-path, and Wi-Fi import units.
3. Disable FTP and any standalone rsync service.
4. Confirm SSH/SFTP works only from the local network.
5. Confirm safe shutdown and recovery after an interrupted boot.
6. Clone a master card only before adding recipient-specific credentials.
7. Keep a tested backup image and written card-recovery instructions.
