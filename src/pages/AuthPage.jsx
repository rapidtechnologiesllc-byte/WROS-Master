import { useState } from "react";
import Login from "../components/Login";
import Signup from "../components/Signup";

export default function AuthPage({ onAuthSuccess }) {
  const [isLogin, setIsLogin] = useState(true);

  return isLogin ? (
        <Login onSwitch={() => setIsLogin(false)} 
        onSuccess={(role) => onAuthSuccess(role)} 
        />
      ) : (
        <Signup onSwitch={() => setIsLogin(true)}
        onSuccess={(role) => onAuthSuccess(role)} 
        />
        
    
  );  
}
