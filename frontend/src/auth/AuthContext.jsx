import {
  createContext,
  useContext,
  useEffect,
  useState,
} from "react";

import {
  login as loginService,
  logout as logoutService,
  register as registerService,
  getStoredUser,
  isAuthenticated,
} from "./authService";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(
    getStoredUser()
  );

  const [loading, setLoading] =
    useState(true);

  useEffect(() => {
    setLoading(false);
  }, []);

  const login = async (
    email,
    password
  ) => {
    const result =
      await loginService(
        email,
        password
      );

    setUser(result.user || null);

    return result;
  };

  const register = async (data) => {
    return registerService(data);
  };

  const logout = () => {
    logoutService();
    setUser(null);
  };

  const value = {
    user,
    setUser,
    loading,
    login,
    register,
    logout,
    isAuthenticated:
      isAuthenticated(),
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context =
    useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuth must be used inside AuthProvider"
    );
  }

  return context;
}

export default AuthContext;