namespace WebServiceInfrastructure
{
    using System;
    using System.Net;
    using System.Net.Sockets;

    /// <summary>
    /// A helper class for Ethernet and WiFi network access. 
    /// </summary>
    public static class Internet
    {
        private static string _localIpv4Address;

        /// <summary>
        /// Gets the URI containing the IP V4 address.
        /// </summary>
        /// <param name="address">The URI containing host name.</param>
        /// <returns>The URI containing the IP V4 address.</returns>
        public static Uri GetIpV4Uri(string address)
        {
            var uri = new UriBuilder(address);
            if (uri.Host.ToLower() == "localhost")
            {
                uri.Host = LocalIpV4Address;
            }
            else if (uri.Port > 0)
            {
                string ipv4 = null;
                var addresses = Dns.GetHostAddresses(uri.Host);
                foreach (var adr in addresses)
                {
                    if (adr.AddressFamily == AddressFamily.InterNetwork && !IPAddress.IsLoopback(adr))
                    {
                        ipv4 = adr.ToString();
                        break;
                    }
                }

                // When no IPv4 address could be found, try a reverse lookup at the DNS. See http://msdn.microsoft.com/en-us/library/ms143998.aspx
                if (ipv4 == null)
                {
                    var hostEntry = Dns.GetHostEntry(uri.Host);
                    foreach (var adr in hostEntry.AddressList)
                    {
                        if (adr.AddressFamily == AddressFamily.InterNetwork && !IPAddress.IsLoopback(adr))
                        {
                            ipv4 = adr.ToString();
                            break;
                        }
                    }
                }

                if (ipv4 != null)
                {
                    uri.Host = ipv4;
                }
            }

            return uri.Uri;
        }

        /// <summary>
        /// Gets the primary ip v4 address of this instrument or computer.
        /// </summary>
        /// <returns>The IP v4 address.</returns>
        public static string LocalIpV4Address
        {
            get
            {
                if (_localIpv4Address == null)
                {
                    _localIpv4Address = ReadLocalIpV4Address();
                }

                return _localIpv4Address;
            }
        }

        private static string ReadLocalIpV4Address()
        {
            var hostEntry = Dns.GetHostEntry(string.Empty); //Dns.GetHostName() returns "compact" on Windows CE
            foreach (var adr in hostEntry.AddressList)
            {
                if (adr.AddressFamily == AddressFamily.InterNetwork)
                {
                    return adr.ToString();
                }
            }

            return "0.0.0.0";
        }
    }
}
