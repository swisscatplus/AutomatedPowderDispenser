namespace WebServiceInfrastructure
{
    using System;
    using System.IO;
    using System.Security.Cryptography;
    using System.Text;

    public static class CryptographyHelper
    {
        public static string DecryptSessionId(string password, string encryptedSessionId, string encodedSalt)
        {
            var encryptedSessionIdData = Convert.FromBase64String(encryptedSessionId);
            var decodedSaltData = Convert.FromBase64String(encodedSalt);
            var key = ComputeKeyFromPassword(password, decodedSaltData);
            var sessionIdData = DecryptEcb(key, encryptedSessionIdData);
            var sessionId = Encoding.UTF8.GetString(sessionIdData);
            return sessionId;
        }

        public static string EncryptPassword(string userPassword, string webServicePassword, string salt)
        {
            var saltAsBytes = Encoding.ASCII.GetBytes(salt);
            var encryptionKey = ComputeKeyFromPassword(webServicePassword, saltAsBytes);
            var plainDataAsBytes = Encoding.ASCII.GetBytes(userPassword);

            var cipherDataAsString = EncryptEcb(encryptionKey, plainDataAsBytes);
            return cipherDataAsString;
        }

        private static string EncryptEcb(byte[] key, byte[] src)
        {
            using (var rijndaelManaged = new RijndaelManaged {KeySize = 256, Padding = PaddingMode.PKCS7, Mode = CipherMode.ECB})
            {
                using (var cryptoTransform = rijndaelManaged.CreateEncryptor(key, null))
                {
                    var dest = cryptoTransform.TransformFinalBlock(src, 0, src.Length);
                    return Convert.ToBase64String(dest);
                }
            }
        }

        private static byte[] DecryptEcb(byte[] key, byte[] data)
        {
            using (var memoryStream = new MemoryStream())
            {
                using (var rijndaelManaged = new RijndaelManaged())
                {
                    rijndaelManaged.Key = key;
                    rijndaelManaged.Mode = CipherMode.ECB;
                    using (var cryptoStream = new CryptoStream(memoryStream, rijndaelManaged.CreateDecryptor(), CryptoStreamMode.Write))
                    {
                        cryptoStream.Write(data, 0, data.Length);
                        cryptoStream.FlushFinalBlock();
                        return memoryStream.ToArray();
                    }
                }
            }
        }

        private static byte[] ComputeKeyFromPassword(string password, byte[] saltData)
        {
            var passwordData = Encoding.UTF8.GetBytes(password);
            var key = GetEncryptionKeyFromPassword(passwordData, saltData);
            return key;
        }

        private static byte[] GetEncryptionKeyFromPassword(byte[] password, byte[] salt)
        {
            var keyGen = new Rfc2898DeriveBytes(password, salt, 1000); // 1000 fix
            var key = keyGen.GetBytes(32);
            return key;
        }
    }
}

